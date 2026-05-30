"""
Centralized DB connection and health checks.

Uses chat_saude.config.settings with fallback to legacy env vars (SQL_*, MONGO_*, VECTOR_*).

This module serves two purposes:
1. Lightweight health-check functions (test_sql, test_nosql, test_vector) used by the UI
   to report the live status of each backend without raising exceptions to the caller.
2. Raw connection helpers (get_db_connection, get_mongo_db) used by ingestion scripts
   that need a low-level cursor or a MongoDB database handle rather than an ORM session.

Configuration priority for each parameter: environment variable > settings object > hardcoded default.
"""

import os

import chromadb
import psycopg2
from pymongo import MongoClient

from chat_saude.config.settings import settings

# ---------------------------------------------------------------------------
# Private parameter helpers
# Each helper checks a legacy env var first so that deployments that set
# SQL_HOST / MONGO_HOST / VECTOR_HOST directly keep working without changes
# to the settings object.
# ---------------------------------------------------------------------------


def _pg_host():
    return os.getenv("SQL_HOST") or getattr(settings, "POSTGRES_HOST", "localhost")


def _pg_port():
    return int(os.getenv("SQL_PORT") or getattr(settings, "POSTGRES_PORT", "5432"))


def _pg_db():
    return os.getenv("SQL_DB") or getattr(settings, "POSTGRES_DB", "db_saude")


def _pg_user():
    return os.getenv("SQL_USER") or getattr(settings, "POSTGRES_USER", "")


def _pg_password():
    return os.getenv("SQL_PASSWORD") or getattr(settings, "POSTGRES_PASSWORD", "")


def _mongo_host():
    return os.getenv("MONGO_HOST") or getattr(settings, "MONGO_HOST", "localhost")


def _mongo_port():
    return int(os.getenv("MONGO_PORT") or getattr(settings, "MONGO_PORT", "27017"))


def _vector_host():
    return os.getenv("VECTOR_HOST") or getattr(settings, "VECTOR_DB_HOST", "localhost")


def _vector_port():
    return int(os.getenv("VECTOR_PORT") or getattr(settings, "VECTOR_DB_PORT", "8010"))


# ---------------------------------------------------------------------------
# Health checks (used by UI)
# Each function attempts a minimal round-trip to its backend and returns a
# plain bool so the caller never has to handle exceptions.  The short
# timeouts (3 s) are intentional — a health check must not block the UI.
# ---------------------------------------------------------------------------


def test_sql():
    """Return True if a TCP connection to PostgreSQL can be established within 3 s."""
    try:
        conn = psycopg2.connect(
            host=_pg_host(),
            port=_pg_port(),
            database=_pg_db(),
            user=_pg_user(),
            password=_pg_password(),
            connect_timeout=3,
        )
        conn.close()
        return True
    except Exception:
        return False


def test_nosql():
    """Return True if MongoDB responds to an admin ping within 3 s."""
    try:
        client = MongoClient(
            host=_mongo_host(),
            port=_mongo_port(),
            username=os.getenv("MONGO_USER"),
            password=os.getenv("MONGO_PASSWORD"),
            serverSelectionTimeoutMS=3000,
        )
        client.admin.command("ping")
        return True
    except Exception:
        return False


def test_vector():
    """Return True if the ChromaDB HTTP server responds to a heartbeat within 3 s."""
    try:
        client = chromadb.HttpClient(host=_vector_host(), port=_vector_port())
        client.heartbeat()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Raw connection helpers (for ingestion scripts)
# These return low-level handles rather than ORM sessions so that ingestion
# scripts can use COPY, executemany, or direct collection access for bulk
# data loading without the overhead of an ORM.
# ---------------------------------------------------------------------------


def get_db_connection():
    """Return a raw psycopg2 connection to PostgreSQL.

    Supports SQL_* and POSTGRES_* env vars.  Callers are responsible for
    committing, rolling back, and closing the connection.
    """
    return psycopg2.connect(
        host=_pg_host(),
        port=_pg_port(),
        database=_pg_db(),
        user=_pg_user(),
        password=_pg_password(),
    )


def get_mongo_db():
    """Return a MongoDB database handle for the configured database.

    Uses MONGO_* env vars (host, port, user, password, db).  The returned
    object is a pymongo Database, not a client, so callers can access
    collections directly (e.g. db["patients"]).

    The 5 s server-selection timeout is longer than the health-check timeout
    because ingestion operations need a little more headroom to start.
    """
    client = MongoClient(
        host=_mongo_host(),
        port=_mongo_port(),
        username=os.getenv("MONGO_USER"),
        password=os.getenv("MONGO_PASSWORD"),
        serverSelectionTimeoutMS=5000,
    )
    return client[os.getenv("MONGO_DB", "db_saude_nosql")]
