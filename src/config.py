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


def _parse_sa_json(raw: str) -> dict:
    """Extract just the first JSON object, ignoring any trailing garbage
    (e.g., a stray DRY_RUN=false line copied into the secret)."""
    obj, _ = json.JSONDecoder().raw_decode(raw.strip())
    if not isinstance(obj, dict):
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON did not decode to an object")
    return obj


def load_settings() -> Settings:
    return Settings(
        telegram_bot_token=_require_env("TELEGRAM_BOT_TOKEN").strip(),
        telegram_chat_id=_require_env("TELEGRAM_CHAT_ID").strip(),
        sheets_id=_require_env("GOOGLE_SHEETS_ID").strip(),
        google_sa_info=_parse_sa_json(_require_env("GOOGLE_SERVICE_ACCOUNT_JSON")),
        dry_run=os.environ.get("DRY_RUN", "false").strip().lower() == "true",
    )
