"""Application configuration loaded from environment variables.

Centralised here so any module can read settings via the cached `get_settings()`
helper without re-reading the environment.
"""

from functools import lru_cache
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the FastAPI service."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Supabase
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_service_key: str = Field(default="", alias="SUPABASE_SERVICE_KEY")

    # Telegram
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")

    # CORS
    allowed_origins: str = Field(
        default="http://localhost:3000",
        alias="ALLOWED_ORIGINS",
    )

    # Dry run disables Supabase writes (helpful for local frontend iteration)
    dry_run: bool = Field(default=False, alias="DEADZONE_DRY_RUN")

    @field_validator("supabase_url", "supabase_service_key", "telegram_bot_token")
    @classmethod
    def _strip(cls, v: str) -> str:
        return (v or "").strip()

    @property
    def origins_list(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def has_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_key)

    @property
    def has_telegram(self) -> bool:
        return bool(self.telegram_bot_token)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()
