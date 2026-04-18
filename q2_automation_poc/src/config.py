from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass
class AppConfig:
    platform_name: str
    platform_url: str
    character_url: str
    test_username: str
    test_password: str
    headless: bool
    slow_mo_ms: int
    output_dir: str
    message_delay_seconds: float
    response_timeout_seconds: float


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_config(env_path: str | None = None) -> AppConfig:
    if env_path:
        load_dotenv(env_path)
    else:
        load_dotenv()

    return AppConfig(
        platform_name=os.getenv("PLATFORM_NAME", ""),
        platform_url=os.getenv("PLATFORM_URL", ""),
        character_url=os.getenv("CHARACTER_URL", ""),
        test_username=os.getenv("TEST_USERNAME", ""),
        test_password=os.getenv("TEST_PASSWORD", ""),
        headless=_to_bool(os.getenv("HEADLESS"), False),
        slow_mo_ms=int(os.getenv("SLOW_MO_MS", "250")),
        output_dir=os.getenv("OUTPUT_DIR", "outputs"),
        message_delay_seconds=float(os.getenv("MESSAGE_DELAY_SECONDS", "1")),
        response_timeout_seconds=float(os.getenv("RESPONSE_TIMEOUT_SECONDS", "60")),
    )

