"""
GHO (Global Health Observatory) API ingestion.
Fetches indicators, dimensions, and dimension values; stores them in MongoDB.
"""

import os
import sys

import requests
from dotenv import load_dotenv
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError

from chat_saude.infrastructure.database.db_connection import get_mongo_db

load_dotenv()

GHO_BASE_URL = "https://ghoapi.azureedge.net/api"

# Collection names for GHO data
COLLECTION_INDICATORS = "gho_indicators"
COLLECTION_DIMENSIONS = "gho_dimensions"


def _mongo_config():
    """Return current MongoDB config (password masked) for debugging."""
    return {
        "MONGO_HOST": os.getenv("MONGO_HOST", "localhost"),
        "MONGO_PORT": os.getenv("MONGO_PORT", "27017"),
        "MONGO_USER": os.getenv("MONGO_USER") or "(not set)",
        "MONGO_PASSWORD": "***" if os.getenv("MONGO_PASSWORD") else "(not set)",
        "MONGO_DB": os.getenv("MONGO_DB", "db_saude_nosql"),
    }


def verify_mongo_connection(db=None) -> tuple[bool, str]:
    """
    Verify MongoDB connection: ping server and list collections.
    Returns (success: bool, message: str). Useful for debugging connection issues.
    """
    try:
        if db is None:
            db = get_mongo_db()
        # Force a round-trip to the server (ping)
        db.client.admin.command("ping")
        # Optional: list collections to ensure we can read from the database
        _ = list(db.list_collection_names())
        return True, "MongoDB connection OK (ping + list_collections succeeded)."
    except ServerSelectionTimeoutError as e:
        return False, (f"MongoDB connection failed (timeout): {e}. Check MONGO_HOST, MONGO_PORT, network, and that MongoDB is running.")
    except OperationFailure as e:
        return False, (f"MongoDB auth or command failed: {e}. Check MONGO_USER and MONGO_PASSWORD (and that the user exists in the DB).")
    except Exception as e:
        return False, f"MongoDB connection error: {type(e).__name__}: {e}"


def fetch_indicators() -> list[dict]:
    """Fetch all indicators from GHO API."""
    url = f"{GHO_BASE_URL}/Indicator"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("value", [])


def fetch_dimensions() -> list[dict]:
    """Fetch all dimensions from GHO API."""
    url = f"{GHO_BASE_URL}/Dimension"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("value", [])


def fetch_dimension_values(dimension_code: str) -> list[dict]:
    """Fetch dimension values for a given dimension code."""
    url = f"{GHO_BASE_URL}/DIMENSION/{dimension_code}/DimensionValues"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data.get("value", [])


def ingest_to_mongo(db=None, skip_connection_check: bool = False):
    """
    Fetch all GHO data and store in MongoDB collections.
    Uses collections:
      - gho_indicators
      - gho_dimensions
      - one collection per dimension values set, e.g.:
          gho_country_dimension_values, gho_agegroup_dimension_values, ...

    Before inserting new dimension values, all existing collections that match
    the pattern gho_*_dimension_values are dropped to avoid stale data.

    If skip_connection_check is False (default), verifies DB connection first and exits on failure.
    """
    if db is None:
        db = get_mongo_db()

    if not skip_connection_check:
        ok, msg = verify_mongo_connection(db)
        if not ok:
            print("ERROR:", msg, file=sys.stderr)
            sys.exit(1)
        print("[DEBUG] DB connection verified.")

    # 1. Indicators
    indicators = fetch_indicators()
    coll_indicators = db[COLLECTION_INDICATORS]
    coll_indicators.delete_many({})
    if indicators:
        coll_indicators.insert_many(indicators)

    # 2. Dimensions
    dimensions = fetch_dimensions()
    coll_dimensions = db[COLLECTION_DIMENSIONS]
    coll_dimensions.delete_many({})
    if dimensions:
        coll_dimensions.insert_many(dimensions)

    total_dim_values = 0
    for dim in dimensions:
        code = dim.get("Code")
        if not code:
            continue
        # Normalize code to build collection name, e.g. "Country" -> "gho_country_dimension_values"
        safe_code = str(code).strip().lower().replace(" ", "_")
        collection_name = f"gho_{safe_code}_dimension_values"
        try:
            values = fetch_dimension_values(code)
            for v in values:
                v["_dimension_code"] = code  # allow filtering by dimension
            if values:
                coll_dim_values = db[collection_name]
                coll_dim_values.delete_many({})
                coll_dim_values.insert_many(values)
                total_dim_values += len(values)
        except requests.RequestException:
            # skip dimension if request fails
            continue

    return {
        "indicators": len(indicators),
        "dimensions": len(dimensions),
        "dimension_values": total_dim_values,
    }


if __name__ == "__main__":
    print("[DEBUG] MongoDB config:", _mongo_config())
    ok, msg = verify_mongo_connection()
    print("[DEBUG]", msg)
    if not ok:
        print("Aborting: fix the connection and run again.", file=sys.stderr)
        sys.exit(1)
    result = ingest_to_mongo()
    print("Ingestion done:", result)
