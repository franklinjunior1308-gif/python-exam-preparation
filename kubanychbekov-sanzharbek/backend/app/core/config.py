from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (see .env.example)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://fixflow:fixflow@localhost:5432/fixflow"
    # demo-only default (32+ bytes so JWT does not warn); never use it in production
    secret_key: str = "dev-only-change-me-dev-only-change-me-0000"
    access_token_minutes: int = 60
    cors_origins: str = "http://localhost:3000"
    upload_dir: str = "./uploads"
    # SEC-03: this many failed sign-ins for one e-mail lock it for the window
    login_max_failures: int = 5
    login_window_minutes: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()
