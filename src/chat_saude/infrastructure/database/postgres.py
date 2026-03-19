import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine

from chat_saude.config.settings import settings


def get_engine():
    """Build and return a SQLAlchemy engine for PostgreSQL using centralized settings."""
    user = os.getenv("SQL_USER") or settings.POSTGRES_USER
    password = os.getenv("SQL_PASSWORD") or settings.POSTGRES_PASSWORD
    host = os.getenv("SQL_HOST") or settings.POSTGRES_HOST
    port = os.getenv("SQL_PORT") or settings.POSTGRES_PORT
    database = os.getenv("SQL_DB") or settings.POSTGRES_DB

    uri = (
        f"postgresql://{quote_plus(str(user))}:{quote_plus(str(password))}"
        f"@{host}:{port}/{database}"
    )
    return create_engine(uri)
