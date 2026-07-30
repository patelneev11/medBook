from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # ── Database ──────────────────────────────────────────────────────────────
    # Full SQLAlchemy connection URL. Use postgresql+asyncpg:// for async driver.
    database_url: str

    # ── Authentication ────────────────────────────────────────────────────────
    # Long random string — generate with: python -c "import secrets; print(secrets.token_hex(32))"
    secret_key: str
    # JWT signing algorithm
    algorithm: str = "HS256"
    # How long access tokens live (minutes)
    access_token_expire_minutes: int = 60
    # How long refresh tokens live (days)
    refresh_token_expire_days: int = 30

    # ── AWS S3 ────────────────────────────────────────────────────────────────
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_bucket_name: str = ""
    aws_region: str = "us-east-1"

    # ── AI ────────────────────────────────────────────────────────────────────
    anthropic_api_key: str = ""

    # ── Background jobs ───────────────────────────────────────────────────────
    # Redis, used as both the Celery broker and result backend
    redis_url: str = "redis://localhost:6379/0"

    # ── App behaviour ─────────────────────────────────────────────────────────
    # "development" | "staging" | "production"
    environment: str = "development"
    # Comma-separated CORS origins — stored as str, parsed via cors_origins property
    allowed_origins: str = "http://localhost:3000,http://localhost:3001"
    # Maximum file upload size in megabytes
    max_upload_size_mb: int = 50
    # API rate limit per minute per IP
    rate_limit_per_minute: int = 60

    @field_validator("secret_key")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters")
        return v

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


settings = Settings()
