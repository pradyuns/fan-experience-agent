import uuid
from datetime import datetime, timezone

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
async def test_get_plan(plan_with_version):
    session, plan_id, _ = plan_with_version
    app = _make_client(session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/plans/{plan_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ACTIVE"
    assert len(data["versions"]) == 1
    assert data["versions"][0]["shortlist"][0]["candidate_id"] == "rest-001"


@pytest.mark.asyncio
async def test_get_plan_not_found(db_session):
    app = _make_client(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/plans/{uuid.uuid4()}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_refine_plan(plan_with_version):
    session, plan_id, _ = plan_with_version
    app = _make_client(session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/plans/{plan_id}/refine",
            json={
                "message": "cheaper options please",
                "structured_preferences": {"price_range": "low"},
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "refine_queued"


@pytest.mark.asyncio
async def test_refine_plan_not_found(db_session):
    app = _make_client(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/plans/{uuid.uuid4()}/refine",
            json={"message": "test"},
        )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_feedback(plan_with_version):
    session, plan_id, _ = plan_with_version
    app = _make_client(session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/plans/{plan_id}/feedback",
            json={"rating": 5, "comment": "Great pick!"},
        )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_feedback_not_found(db_session):
    app = _make_client(db_session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/plans/{uuid.uuid4()}/feedback",
            json={"rating": 3},
        )

    assert response.status_code == 404
