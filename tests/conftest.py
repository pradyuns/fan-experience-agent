import pytest

from fan_experience.config import Settings


@pytest.fixture
# building isolated settings for tests.
def test_settings():
    return Settings(
        database_url="sqlite+aiosqlite:///",
        redis_url="redis://localhost:6379/1",
        anthropic_api_key="test-key",
        webhook_hmac_secret="test-secret",
    )
