"""
YieldLens AI — Shared Configuration
Loaded from environment variables / .env file.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="postgresql+asyncpg://yieldlens:yieldlens@localhost:5432/yieldlens"
    )
    database_url_sync: str = Field(
        default="postgresql://yieldlens:yieldlens@localhost:5432/yieldlens"
    )

    # ── FRED ──────────────────────────────────────────────────────────────────
    fred_api_key: str = Field(default="")

    # ── OpenAI ────────────────────────────────────────────────────────────────
    openai_api_key: str = Field(default="")
    openai_model: str = Field(default="gpt-4o-mini")

    # ── Embedding ─────────────────────────────────────────────────────────────
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    embedding_dim: int = Field(default=384)

    # ── Retrieval ─────────────────────────────────────────────────────────────
    retrieval_candidate_k: int = Field(default=50)
    retrieval_final_k: int = Field(default=10)
    reranker_model: str = Field(default="cross-encoder/ms-marco-MiniLM-L-6-v2")

    # ── MLflow ────────────────────────────────────────────────────────────────
    mlflow_tracking_uri: str = Field(default="http://localhost:5001")
    mlflow_experiment_name: str = Field(default="yieldlens-eval")

    # ── Fed scraper ───────────────────────────────────────────────────────────
    fed_scraper_delay_seconds: float = Field(default=1.5)
    fed_base_url: str = Field(default="https://www.federalreserve.gov")
    fomc_calendar_url: str = Field(
        default="https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
    )

    # ── API ───────────────────────────────────────────────────────────────────
    api_secret_key: str = Field(default="change-me-in-production")
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000)

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = Field(default="INFO")


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (loaded once per process)."""
    return Settings()


settings = get_settings()

