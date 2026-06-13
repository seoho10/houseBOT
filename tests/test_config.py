import os
import json
import pytest
from src.config import Settings, load_settings


def test_load_settings_from_env(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok123")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "456")
    monkeypatch.setenv("GOOGLE_SHEETS_ID", "sheetid")
    sa_json = json.dumps({"type": "service_account", "client_email": "a@b.com"})
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", sa_json)
    monkeypatch.setenv("DRY_RUN", "false")

    s = load_settings()

    assert s.telegram_bot_token == "tok123"
    assert s.telegram_chat_id == "456"
    assert s.sheets_id == "sheetid"
    assert s.google_sa_info["client_email"] == "a@b.com"
    assert s.dry_run is False


def test_load_settings_dry_run_true(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "456")
    monkeypatch.setenv("GOOGLE_SHEETS_ID", "sheetid")
    monkeypatch.setenv("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
    monkeypatch.setenv("DRY_RUN", "true")

    s = load_settings()
    assert s.dry_run is True


def test_load_settings_missing_raises(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        load_settings()
