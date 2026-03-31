import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from fan_experience.api.app import create_app


def _make_client(session):
    app = create_app()

    async def override_get_db():
        yield session

    from fan_experience.api.deps import get_db

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.mark.asyncio
async def test_get_user_preferences(user_with_prefs):
    session, user_id = user_with_prefs
    app = _make_client(session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/users/{user_id}/preferences")

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == str(user_id)
    assert len(data["preferences"]) == 2


@pytest.mark.asyncio
async def test_get_preferences_empty(db_session):
    app = _make_client(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/users/{uuid.uuid4()}/preferences")

    assert response.status_code == 200
    assert response.json()["preferences"] == []
