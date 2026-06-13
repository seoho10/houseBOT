"""Environment-based settings and apartment config types."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    telegram_chat_id: str
    sheets_id: str
    google_sa_info: dict
    dry_run: bool


@dataclass(frozen=True)
class ApartmentConfig:
    name: str
    complex_id: str
    interested_sizes: tuple[str, ...]
    active: bool


def _require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise RuntimeError(f"Missing required environment variable: {key}")
    return val


def load_settings() -> Settings:
    return Settings(
        telegram_bot_token=_require_env("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=_require_env("TELEGRAM_CHAT_ID"),
        sheets_id=_require_env("GOOGLE_SHEETS_ID"),
        google_sa_info=json.loads(_require_env("GOOGLE_SERVICE_ACCOUNT_JSON").strip()),
        dry_run=os.environ.get("DRY_RUN", "false").strip().lower() == "true",
    )
