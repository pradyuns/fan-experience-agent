from fan_experience.config import Settings


def test_settings_loads_local_dotenv(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("FAN_ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("FAN_WEBHOOK_HMAC_SECRET", raising=False)

    (tmp_path / ".env").write_text(
        "FAN_ANTHROPIC_API_KEY=dotenv-key\n"
        "FAN_WEBHOOK_HMAC_SECRET=dotenv-secret\n",
        encoding="utf-8",
    )

    loaded = Settings()

    assert loaded.anthropic_api_key == "dotenv-key"
    assert loaded.webhook_hmac_secret == "dotenv-secret"
