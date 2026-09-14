from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    app_name: str = "Персональный AI-ассистент Андриса Янчевскиса"
    app_env: str = "development"
    openai_api_key: Optional[str] = None
    llm_model: str = ""
    embedding_model: str = ""
    vector_db_path: str = "./data/qdrant"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
