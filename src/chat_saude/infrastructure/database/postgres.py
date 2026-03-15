from urllib.parse import quote_plus

from sqlalchemy import create_engine

from chat_saude.config.settings import settings


def get_engine():
    """Build and return a SQLAlchemy engine for PostgreSQL using centralized settings."""
    uri = (
        f"postgresql://{quote_plus(settings.POSTGRES_USER)}:{quote_plus(settings.POSTGRES_PASSWORD)}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )
    return create_engine(uri)
