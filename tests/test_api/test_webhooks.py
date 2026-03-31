import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fan_experience.api.app import create_app
from fan_experience.db.models import Base, Event, User


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)

    user_id = uuid.uuid4()
    event_id = uuid.uuid4()
    session.add_all(
        [
            User(id=user_id, name="Fan", email="f@t.com", timezone="UTC"),
            Event(
                id=event_id,
                name="Game",
                venue_name="V",
                venue_address="A",
                venue_lat=34.0,
                venue_lng=-118.0,
                event_time=datetime(2026, 7, 1, 20, 0, tzinfo=timezone.utc),
                doors_open=datetime(2026, 7, 1, 18, 30, tzinfo=timezone.utc),
                genre="sports",
            ),
        ]
    )
    session.commit()
    yield session, user_id, event_id
    session.close()


def _sign(body: bytes, secret: str = "test-secret") -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_webhook_creates_plan(db_session):
    session, user_id, event_id = db_session
    app = create_app()

    async def override_get_db():
        yield session

    from fan_experience.api.deps import get_db

    app.dependency_overrides[get_db] = override_get_db

    body = {
        "purchase_id": "ext-test-001",
        "user_id": str(user_id),
        "event_id": str(event_id),
        "ticket_count": 2,
        "purchased_at": datetime.now(timezone.utc).isoformat(),
    }
    raw_body = json.dumps(body).encode()
    signature = _sign(raw_body)

    with patch("fan_experience.api.webhooks.settings") as mock_settings:
        mock_settings.webhook_hmac_secret = "test-secret"

        with patch("fan_experience.api.webhooks.dispatch_plan_generation") as mock_dispatch:
            mock_dispatch.delay = MagicMock()

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test",
            ) as client:
                response = await client.post(
                    "/webhooks/purchase",
                    content=raw_body,
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Signature": signature,
                    },
                )

    assert response.status_code == 201
    data = response.json()
    assert "plan_id" in data


@pytest.mark.asyncio
async def test_webhook_rejects_bad_signature(db_session):
    session, user_id, event_id = db_session
    app = create_app()

    async def override_get_db():
        yield session

    from fan_experience.api.deps import get_db

    app.dependency_overrides[get_db] = override_get_db

    body = json.dumps(
        {
            "purchase_id": "ext-test-002",
            "user_id": str(user_id),
            "event_id": str(event_id),
            "ticket_count": 1,
            "purchased_at": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()

    with patch("fan_experience.api.webhooks.settings") as mock_settings:
        mock_settings.webhook_hmac_secret = "test-secret"

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/webhooks/purchase",
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": "bad-signature",
                },
            )

    assert response.status_code == 401
