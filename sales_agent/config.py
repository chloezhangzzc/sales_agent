from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


DEFAULT_IDENTITY_HANDLE = "outreach-agent"
DEFAULT_IDENTITY_DISPLAY_NAME = "Chloe"
DEFAULT_IDENTITY_EMAIL = "hirepilot_outreach@inkboxmail.com"
DEFAULT_OPENAI_MODEL = "gpt-5"
DEFAULT_REVIEW_EMAIL = "chloezzx@bu.edu"


def load_local_env(env_path: Path | None = None) -> None:
    """Populate missing environment variables from a local .env file."""
    target_path = env_path or Path.cwd() / ".env"
    if not target_path.exists():
        return

    for raw_line in target_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class InkboxSettings:
    api_key: str
    identity_handle: str = DEFAULT_IDENTITY_HANDLE
    identity_display_name: str = DEFAULT_IDENTITY_DISPLAY_NAME
    identity_email: str = DEFAULT_IDENTITY_EMAIL
    review_email: str = DEFAULT_REVIEW_EMAIL
    live_outreach_enabled: bool = False

    @classmethod
    def from_env(cls) -> "InkboxSettings":
        load_local_env()
        api_key = os.getenv("INKBOX_API_KEY", "").strip()
        if not api_key:
            raise ValueError("Missing required environment variable: INKBOX_API_KEY")

        identity_handle = (
            os.getenv("INKBOX_IDENTITY_HANDLE", DEFAULT_IDENTITY_HANDLE).strip() or DEFAULT_IDENTITY_HANDLE
        )
        identity_display_name = (
            os.getenv("INKBOX_IDENTITY_DISPLAY_NAME", DEFAULT_IDENTITY_DISPLAY_NAME).strip()
            or DEFAULT_IDENTITY_DISPLAY_NAME
        )
        identity_email = os.getenv("INKBOX_IDENTITY_EMAIL", DEFAULT_IDENTITY_EMAIL).strip() or DEFAULT_IDENTITY_EMAIL
        review_email = os.getenv("OUTREACH_REVIEW_EMAIL", DEFAULT_REVIEW_EMAIL).strip() or DEFAULT_REVIEW_EMAIL
        live_outreach_enabled = os.getenv("ALLOW_LIVE_OUTREACH", "").strip().lower() in {"1", "true", "yes"}

        return cls(
            api_key=api_key,
            identity_handle=identity_handle,
            identity_display_name=identity_display_name,
            identity_email=identity_email,
            review_email=review_email,
            live_outreach_enabled=live_outreach_enabled,
        )


@dataclass(frozen=True)
class OpenAISettings:
    api_key: str
    model: str = DEFAULT_OPENAI_MODEL

    @classmethod
    def from_env(cls) -> "OpenAISettings":
        load_local_env()
        api_key = os.getenv("OPENAI_API", "").strip() or os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise ValueError("Missing required environment variable: OPENAI_API or OPENAI_API_KEY")

        model = os.getenv("OPENAI_MODEL", DEFAULT_OPENAI_MODEL).strip() or DEFAULT_OPENAI_MODEL
        return cls(api_key=api_key, model=model)
