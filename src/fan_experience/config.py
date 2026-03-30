from pydantic_settings import BaseSettings


# app-wide settings, loaded from env vars prefixed with FAN_
class Settings(BaseSettings):
    # infrastructure
    database_url: str = "postgresql+asyncpg://localhost:5432/fan_experience"
    redis_url: str = "redis://localhost:6379/0"
    anthropic_api_key: str = ""
    webhook_hmac_secret: str = "dev-secret"

    # adaptation loop tuning
    adaptation_interval_minutes: int = 30
    adaptation_horizon_hours: int = 48
    max_replans_per_plan: int = 5
    replan_cooldown_minutes: int = 60
    post_confirm_cooldown_minutes: int = 120

    model_config = {"env_prefix": "FAN_"}


settings = Settings()
