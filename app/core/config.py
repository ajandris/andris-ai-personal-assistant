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

    # SQLite Messages Database
    sqlite_db_path: str = "./data/messages.db"

    # Google reCAPTCHA
    recaptcha_site_key: str = ""
    recaptcha_secret_key: str = ""

    # SMTP Email Configuration
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_to_email: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
