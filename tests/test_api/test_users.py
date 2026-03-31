import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session

from fan_experience.api.app import create_app
from fan_experience.db.models import User, UserPreference


@pytest.fixture
def seeded_db(db_session: Session):
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, name="Fan", email="f@t.com", timezone="UTC"))
    db_session.add(
        UserPreference(
            id=uuid.uuid4(),
            user_id=user_id,
            preference_type="cuisine",
            value_json={"italian": 0.9},
            confidence=0.8,
        )
    )
    db_session.add(
        UserPreference(
            id=uuid.uuid4(),
            user_id=user_id,
            preference_type="price",
            value_json={"range": "medium"},
            confidence=0.7,
        )
    )
    db_session.commit()
    yield db_session, user_id


@pytest.mark.asyncio
async def test_get_user_preferences(seeded_db):
    session, user_id = seeded_db
    app = create_app()

    async def override_get_db():
        yield session

    from fan_experience.api.deps import get_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/users/{user_id}/preferences")

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(user_id)
    assert len(data["preferences"]) == 2
