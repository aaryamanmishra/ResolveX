"""Application configuration for ResolveX AI.

PRD §12.3: Configuration-driven architecture supporting Demo Mode
with zero required paid keys or third-party infrastructure.
API keys are loaded from environment variables and never checked into source control.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """ResolveX AI configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    DEMO_MODE: bool = True  # When True, simulator and stub models run without API keys
    SECRET_KEY: str = "resolvex-default-dev-secret-key-change-in-prod"

    # Database & Cache
    DATABASE_URL: str = "postgresql://resolvex:resolvex@localhost:5432/resolvex_db"
    VALKEY_URL: str = "redis://localhost:6379/0"

    # Payment Provider Selection ("simulator" or "razorpay")
    PAYMENT_PROVIDER: str = "simulator"
    # --- PRODUCTION API KEYS FOR RAZORPAY ---
    # Set in .env or cloud environment when running live or Razorpay Test Mode:
    RAZORPAY_KEY_ID: str | None = None
    RAZORPAY_KEY_SECRET: str | None = None
    RAZORPAY_WEBHOOK_SECRET: str | None = None

    # Model Provider Selection ("stub", "gemma", "gemini")
    MODEL_PROVIDER: str = "stub"
    # --- PRODUCTION CREDENTIALS FOR GEMMA / GEMINI ---
    # Set when connecting to Google Gemini API:
    GEMINI_API_KEY: str | None = None
    # Set when connecting to deployed Gemma 4 on DigitalOcean GPU Droplet:
    GEMMA_ENDPOINT_URL: str | None = None
    GEMMA_AUTH_TOKEN: str | None = None

    # Graph Engine Selection ("memory", "apache_age", "tigergraph")
    GRAPH_ENGINE: str = "memory"
    # --- OPTIONAL CREDENTIALS FOR TIGERGRAPH ADAPTER ---
    TIGERGRAPH_HOST: str | None = None
    TIGERGRAPH_GRAPH_NAME: str | None = None
    TIGERGRAPH_SECRET: str | None = None
    TIGERGRAPH_TOKEN: str | None = None

    # Object Storage (Spaces / S3)
    SPACES_ENDPOINT: str = "http://localhost:9000"
    SPACES_BUCKET: str = "resolvex-evidence"
    SPACES_ACCESS_KEY: str | None = None
    SPACES_SECRET_KEY: str | None = None


settings = Settings()
