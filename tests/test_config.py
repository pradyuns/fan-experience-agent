from fan_experience.config import Settings


def test_settings_loads_local_dotenv(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FAN_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("FAN_WEBHOOK_HMAC_SECRET", raising=False)
    monkeypatch.delenv("FAN_TELEMETRY_ENABLED", raising=False)
    monkeypatch.delenv("FAN_TELEMETRY_SERVICE_NAME", raising=False)
    monkeypatch.delenv("FAN_TELEMETRY_ENV", raising=False)
    monkeypatch.delenv("FAN_TELEMETRY_LOG_LEVEL", raising=False)
    monkeypatch.delenv("FAN_OTEL_EXPORTER_OTLP_ENDPOINT", raising=False)
    monkeypatch.delenv("FAN_OTEL_TRACE_SAMPLE_RATIO", raising=False)
    monkeypatch.delenv("FAN_OTEL_METRICS_EXPORT_INTERVAL_MS", raising=False)

    (tmp_path / ".env").write_text(
        "FAN_ANTHROPIC_API_KEY=dotenv-key\n"
        "FAN_WEBHOOK_HMAC_SECRET=dotenv-secret\n"
        "FAN_TELEMETRY_ENABLED=false\n"
        "FAN_TELEMETRY_SERVICE_NAME=fan-test\n"
        "FAN_TELEMETRY_ENV=test\n"
        "FAN_TELEMETRY_LOG_LEVEL=DEBUG\n"
        "FAN_OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4318\n"
        "FAN_OTEL_TRACE_SAMPLE_RATIO=0.25\n"
        "FAN_OTEL_METRICS_EXPORT_INTERVAL_MS=5000\n",
        encoding="utf-8",
    )

    loaded = Settings()

    assert loaded.anthropic_api_key == "dotenv-key"
    assert loaded.webhook_hmac_secret == "dotenv-secret"
    assert loaded.telemetry_enabled is False
    assert loaded.telemetry_service_name == "fan-test"
    assert loaded.telemetry_env == "test"
    assert loaded.telemetry_log_level == "DEBUG"
    assert loaded.otel_exporter_otlp_endpoint == "http://collector:4318"
    assert loaded.otel_trace_sample_ratio == 0.25
    assert loaded.otel_metrics_export_interval_ms == 5000
