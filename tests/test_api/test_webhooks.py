import hashlib
import hmac
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session

from fan_experience.api.app import create_app
from fan_experience.db.models import Event, Plan, PlanStatus, Purchase, User


@pytest.fixture
def webhook_db(db_session: Session):
    user_id = uuid.uuid4()
    event_id = uuid.uuid4()
    db_session.add_all(
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
    db_session.commit()
    yield db_session, user_id, event_id


def _sign(body: bytes, secret: str = "test-secret") -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _make_client(session):
    app = create_app()

    async def override_get_db():
        yield session

    from fan_experience.api.deps import get_db

    app.dependency_overrides[get_db] = override_get_db
    return app


def _purchase_body(user_id, event_id, purchase_id="ext-test-001"):
    return json.dumps(
        {
            "purchase_id": purchase_id,
            "user_id": str(user_id),
            "event_id": str(event_id),
            "ticket_count": 2,
            "purchased_at": datetime.now(timezone.utc).isoformat(),
        }
    ).encode()


@pytest.mark.asyncio
async def test_webhook_creates_plan(webhook_db):
    session, user_id, event_id = webhook_db
    app = _make_client(session)

    raw_body = _purchase_body(user_id, event_id)
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
    assert data["status"] == "generating"


@pytest.mark.asyncio
async def test_webhook_rejects_bad_signature(webhook_db):
    session, user_id, event_id = webhook_db
    app = _make_client(session)

    raw_body = _purchase_body(user_id, event_id, purchase_id="ext-test-002")

    with patch("fan_experience.api.webhooks.settings") as mock_settings:
        mock_settings.webhook_hmac_secret = "test-secret"

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/webhooks/purchase",
                content=raw_body,
                headers={
                    "Content-Type": "application/json",
                    "X-Webhook-Signature": "bad-signature",
                },
            )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_webhook_duplicate_purchase(webhook_db):
    session, user_id, event_id = webhook_db

    # pre-seed an existing purchase and plan
    purchase_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    session.add(
        Purchase(
            id=purchase_id,
            user_id=user_id,
            event_id=event_id,
            purchase_id="ext-dup-001",
            ticket_count=2,
            purchased_at=datetime.now(timezone.utc),
        )
    )
    session.add(
        Plan(
            id=plan_id,
            purchase_id=purchase_id,
            user_id=user_id,
            event_id=event_id,
            status=PlanStatus.ACTIVE,
        )
    )
    session.commit()

    app = _make_client(session)
    raw_body = _purchase_body(user_id, event_id, purchase_id="ext-dup-001")
    signature = _sign(raw_body)

    with patch("fan_experience.api.webhooks.settings") as mock_settings:
        mock_settings.webhook_hmac_secret = "test-secret"

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
    assert data["status"] == "already_processed"
    assert data["plan_id"] == str(plan_id)
