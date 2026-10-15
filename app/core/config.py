"""Application configuration module.

Loads environment variables from the root .env file and provides
typed settings to the rest of the application.
"""

from functools import lru_cache
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Path to the project root and .env file
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = ROOT_DIR / ".env"

# Load variables from .env into environment
if ENV_FILE.exists():
    load_dotenv(dotenv_path=ENV_FILE, encoding="utf-8")


class Settings(BaseSettings):
    """Application settings loaded from environment variables and .env file."""

    app_name: str = "Персональный AI-ассистент Андриса Янчевскиса"
    app_env: str = "development"
    openai_api_key: Optional[str] = None
    llm_model: str = ""
    embedding_model: str = ""
    vector_db_path: str = "./rag"

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
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def effective_llm_model(self) -> str:
        """Return usable OpenAI model name, falling back to gpt-4o-mini."""
        val = (self.llm_model or "").strip()
        if not val or val.lower() in ("openai", "default"):
            return "gpt-4o-mini"
        return val

    @property
    def effective_embedding_model(self) -> str:
        """Return usable OpenAI embedding model name, falling back to text-embedding-3-small."""
        val = (self.embedding_model or "").strip()
        if not val or val.lower() in ("openai", "default"):
            return "text-embedding-3-small"
        return val


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings instance loaded from .env."""
    return Settings()


# Default singleton instance for direct imports across the program:
# from app.core.config import settings
settings: Settings = get_settings()
