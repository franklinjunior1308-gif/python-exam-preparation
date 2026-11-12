from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (see .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://fixflow:fixflow@localhost:5432/fixflow"
    secret_key: str = "dev-only-change-me"  # demo-only default, never use in production
    access_token_minutes: int = 60
    cors_origins: str = "http://localhost:3000"
    upload_dir: str = "./uploads"


@lru_cache
def get_settings() -> Settings:
    return Settings()
