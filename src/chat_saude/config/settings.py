"""
Application configuration module.

All runtime settings are resolved from environment variables or a .env file
via Pydantic Settings.  Defaults are chosen for a fully local development
setup so the application can start without any environment customisation.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized configuration loaded from environment and .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",  # .env can contain SQL_*, MONGO_*, VECTOR_* etc. used by db_connection
    )

    # App
    APP_PORT: int = 8501
    API_HOST: str = "localhost"
    API_PORT: int = 8500

    # PostgreSQL
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "db_saude"
    POSTGRES_USER: str = ""
    POSTGRES_PASSWORD: str = ""

    # MongoDB
    MONGO_HOST: str = "localhost"
    MONGO_PORT: int = 27017

    # Vector DB (e.g. Chroma)
    VECTOR_DB_HOST: str = "localhost"
    VECTOR_DB_PORT: int = 8010

    # Ollama
    OLLAMA_HOST: str = "http://localhost:11434"


# Module-level singleton so every import shares the same resolved config.
settings = Settings()
