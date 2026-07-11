from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="POS_", extra="ignore")

    app_name: str = "Indian Retail POS"
    environment: str = "development"
    database_url: str = "postgresql+psycopg2://pos:pos@localhost:5432/pos"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 12
    algorithm: str = "HS256"
    default_country: str = "IN"


@lru_cache
def get_settings() -> Settings:
    return Settings()
