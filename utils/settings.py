"""
Centralized Settings — Single source of truth for all configuration.

Why this matters:
- Previously every agent called os.getenv() independently with different defaults
- If you rename an env var, you'd have to grep across 8 files
- Pydantic validates types at startup (fail fast, not mid-pipeline)
- One place to document every config knob the project supports

Usage (anywhere in the codebase):
    from utils.settings import settings

    client = Groq(api_key=settings.GROQ_API_KEY)
    engine = create_engine(settings.DATABASE_URL)
"""

import os
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """
    Application-wide configuration, loaded from environment variables / .env.

    Pydantic validates every field on startup.  If a required variable is
    missing or has the wrong type the process exits immediately with a clear
    error — not halfway through processing invoice #47.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore unknown env vars (e.g., PATH, HOME)
    )

    # ── LLM ──
    GROQ_API_KEY: str = Field(..., description="Groq API key (required)")
    GROQ_MODEL: str = Field(
        default="llama-3.3-70b-versatile",
        description="Groq model ID to use for classification and extraction",
    )

    # ── Apify ──
    APIFY_API_TOKEN: Optional[str] = Field(
        default=None,
        description="Apify API token. If unset, mock mode is used automatically.",
    )
    USE_MOCK_APIFY: bool = Field(
        default=True,
        description="Use mock freight rates instead of live Apify scraping",
    )

    # ── Database ──
    DATABASE_URL: str = Field(
        default="sqlite:///cpa_agent.db",
        description="SQLAlchemy database URL",
    )

    # ── Benchmarking ──
    BENCHMARK_THRESHOLD_PERCENT: float = Field(
        default=15.0,
        description="Deviation threshold (%) above which a price is flagged as overpriced",
    )

    # ── Caching ──
    CACHE_TTL_HOURS: float = Field(
        default=24.0,
        description="How long to keep Docling + LLM cache entries (hours)",
    )

    # ── Logging ──
    LOG_LEVEL: str = Field(
        default="INFO",
        description="Python logging level: DEBUG, INFO, WARNING, ERROR",
    )

    @field_validator("LOG_LEVEL")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper = v.upper()
        if upper not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {allowed}, got '{v}'")
        return upper

    @field_validator("BENCHMARK_THRESHOLD_PERCENT")
    @classmethod
    def validate_threshold(cls, v: float) -> float:
        if v <= 0 or v > 100:
            raise ValueError("BENCHMARK_THRESHOLD_PERCENT must be between 0 and 100")
        return v


# ── Global singleton ──
# Import this wherever you need config — no more os.getenv() scattered around.
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Return the global Settings singleton (lazy-initialized)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Convenience alias: `from utils.settings import settings`
settings = get_settings()
