import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fan_experience.config import Settings, settings
from fan_experience.db.models import Base
from fan_experience.telemetry.metrics import reset_metric_events

settings.telemetry_enabled = False


@pytest.fixture
def test_settings():
    return Settings(
        database_url="sqlite+aiosqlite:///",
        redis_url="redis://localhost:6379/1",
        anthropic_api_key="test-key",
        webhook_hmac_secret="test-secret",
    )


@pytest.fixture(autouse=True)
def disable_runtime_exporters():
    settings.telemetry_enabled = False
    yield
    settings.telemetry_enabled = False


@pytest.fixture(autouse=True)
def reset_telemetry_metrics():
    reset_metric_events()
    yield
    reset_metric_events()


# in-memory sqlite for model tests (sync, no postgres needed)
@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()
