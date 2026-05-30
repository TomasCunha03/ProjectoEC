"""
SQLAlchemy engine factory for PostgreSQL in the chat_saude infrastructure layer.

Provides a single entry point for creating a SQLAlchemy engine whose
connection parameters are resolved from environment variables (SQL_*)
with a fallback to the centralized settings object.  The URL-encoding of
the credentials ensures that special characters in passwords do not break
the connection string.
"""

import os
from urllib.parse import quote_plus

from sqlalchemy import create_engine

from chat_saude.config.settings import settings


def get_engine():
    """Build and return a SQLAlchemy engine for PostgreSQL using centralized settings.

    Connection parameters are resolved with the following priority:
    environment variable (SQL_*) > settings object > implicit SQLAlchemy default.

    The username and password are percent-encoded with quote_plus so that
    characters such as '@', '/', or '+' in the credentials do not corrupt the
    connection URL.

    Returns:
        sqlalchemy.engine.Engine: A SQLAlchemy engine that can be used to
        obtain connections or passed to ORM session factories.
    """
    user = os.getenv("SQL_USER") or settings.POSTGRES_USER
    password = os.getenv("SQL_PASSWORD") or settings.POSTGRES_PASSWORD
    host = os.getenv("SQL_HOST") or settings.POSTGRES_HOST
    port = os.getenv("SQL_PORT") or settings.POSTGRES_PORT
    database = os.getenv("SQL_DB") or settings.POSTGRES_DB

    # quote_plus encodes special characters in user/password so they are safe
    # to embed directly in the URL without breaking the postgresql:// scheme.
    uri = f"postgresql://{quote_plus(str(user))}:{quote_plus(str(password))}@{host}:{port}/{database}"
    return create_engine(uri)
