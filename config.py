"""Central configuration for Crypto-Spikes.

This module provides a small, explicit configuration layer for the project.
It prefers environment variables and stays dependency-light so the existing
codebase can adopt it incrementally.
"""
from __future__ import annotations

from dataclasses import dataclass
import os
from typing import List


@dataclass(frozen=True)
class Settings:
    """Application settings loaded from environment variables."""

    app_name: str = "Crypto-Spikes"
    app_env: str = "development"
    log_level: str = "INFO"
    scan_interval_seconds: int = 3600
    max_tracked_coins: int = 25
    spot_only: bool = True
    alert_channels: str = "telegram"

    @property
    def tracked_coins(self) -> List[str]:
        raw = os.getenv("TRACKED_COINS", "")
        return [coin.strip() for coin in raw.split(",") if coin.strip()]


REQUIRED_ENV_VARS = (
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
)


def load_settings() -> Settings:
    """Load settings from environment variables."""

    return Settings(
        app_name=os.getenv("APP_NAME", "Crypto-Spikes"),
        app_env=os.getenv("APP_ENV", "development"),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
        scan_interval_seconds=int(os.getenv("SCAN_INTERVAL_SECONDS", "3600")),
        max_tracked_coins=int(os.getenv("MAX_TRACKED_COINS", "25")),
        spot_only=os.getenv("SPOT_ONLY", "true").lower() in {"1", "true", "yes", "on"},
        alert_channels=os.getenv("ALERT_CHANNELS", "telegram"),
    )


def validate_environment() -> None:
    """Raise a clear error if required env vars are missing."""

    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")
