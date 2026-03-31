from pydantic_settings import BaseSettings, SettingsConfigDict


# app-wide settings, loaded from env vars prefixed with FAN_
class Settings(BaseSettings):
    # infrastructure
    database_url: str = "postgresql+asyncpg://fan_experience:fan_experience@localhost:5432/fan_experience"
    redis_url: str = "redis://localhost:6379/0"
    anthropic_api_key: str = ""
    webhook_hmac_secret: str = "dev-secret"

    # telemetry
    telemetry_enabled: bool = True
    telemetry_service_name: str = "fan-experience-agent"
    telemetry_env: str = "dev"
    telemetry_log_level: str = "INFO"
    otel_exporter_otlp_endpoint: str = "http://localhost:4318"
    otel_trace_sample_ratio: float = 1.0
    otel_metrics_export_interval_ms: int = 10000

    # adaptation loop tuning
    adaptation_interval_minutes: int = 30
    adaptation_horizon_hours: int = 48
    max_replans_per_plan: int = 5
    replan_cooldown_minutes: int = 60
    post_confirm_cooldown_minutes: int = 120

    model_config = SettingsConfigDict(
        env_prefix="FAN_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
