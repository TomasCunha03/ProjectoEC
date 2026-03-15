"""
Centralized DB connection and health checks.
Uses chat_saude.config.settings with fallback to legacy env vars (SQL_*, MONGO_*, VECTOR_*).
"""
import os

import chromadb
import psycopg2
from pymongo import MongoClient

from chat_saude.config.settings import settings


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
    return int(os.getenv("VECTOR_PORT") or getattr(settings, "VECTOR_DB_PORT", "8002"))


# --- Health checks (used by UI) ---
def test_sql():
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
    try:
        client = chromadb.HttpClient(host=_vector_host(), port=_vector_port())
        client.heartbeat()
        return True
    except Exception:
        return False


# --- PostgreSQL raw connection (for ingestion scripts using cursor) ---
def get_db_connection():
    """Return a raw psycopg2 connection to PostgreSQL. Supports SQL_* and POSTGRES_* env."""
    return psycopg2.connect(
        host=_pg_host(),
        port=_pg_port(),
        database=_pg_db(),
        user=_pg_user(),
        password=_pg_password(),
    )


# --- MongoDB database (for ingestion scripts that need auth + db name) ---
def get_mongo_db():
    """Return MongoDB database instance. Uses MONGO_* env (host, port, user, password, db)."""
    client = MongoClient(
        host=_mongo_host(),
        port=_mongo_port(),
        username=os.getenv("MONGO_USER"),
        password=os.getenv("MONGO_PASSWORD"),
        serverSelectionTimeoutMS=5000,
    )
    return client[os.getenv("MONGO_DB", "db_saude_nosql")]
