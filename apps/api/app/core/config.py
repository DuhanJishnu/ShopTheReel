"""Application settings (pydantic-settings). Single source for env config."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "dev"
    database_url: str = "postgresql+asyncpg://shop:shop@localhost:5432/shopthereel"
    redis_url: str = "redis://localhost:6379/0"
    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "shopthereel"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_region: str = "auto"  # Cloudflare R2 requires "auto"; S3/MinIO accept any
    jwt_secret: str = "change-me"
    jwt_access_minutes: int = 15
    jwt_refresh_days: int = 30
    gemini_api_key: str = ""
    gemini_vision_model: str = "gemini-3.8-flash"  # 2.5-flash retired (API 404, Oct 2026); names change, keep in env
    google_allowed_client_ids: str = ""  # comma-separated OAuth client IDs accepted as token audience
    gemini_embed_model: str = "gemini-embedding-001"
    max_video_mb: int = 100
    max_video_seconds: int = 90


settings = Settings()
