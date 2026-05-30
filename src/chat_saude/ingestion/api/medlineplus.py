"""
MedlinePlus API ingestion.
Fetches health topic summaries for all diseases in the PostgreSQL
'diseases' table and stores them in MongoDB.
"""

import sys
import xml.etree.ElementTree as ET

import requests
from dotenv import load_dotenv
from pymongo.errors import OperationFailure, ServerSelectionTimeoutError

from chat_saude.infrastructure.database.db_connection import get_db_connection, get_mongo_db

load_dotenv()

MEDLINE_BASE_URL = "https://wsearch.nlm.nih.gov/ws/query"
COLLECTION_NAME = "medlineplus_health_topics"


def verify_mongo_connection(db=None) -> tuple[bool, str]:
    """
    Ping MongoDB and return a (success, message) tuple.

    Parameters
    ----------
    db :
        An existing MongoDB database handle.  A new connection is opened when
        not provided.

    Returns
    -------
    tuple[bool, str]
        ``(True, ok_message)`` on success or ``(False, error_message)`` on
        failure.  Useful for early-exit checks before starting long ingestion
        runs.
    """
    try:
        if db is None:
            db = get_mongo_db()
        db.client.admin.command("ping")
        return True, "MongoDB connection OK."
    except ServerSelectionTimeoutError as e:
        return False, f"MongoDB connection failed (timeout): {e}"
    except OperationFailure as e:
        return False, f"MongoDB auth failed: {e}"
    except Exception as e:
        return False, f"MongoDB connection error: {type(e).__name__}: {e}"


def fetch_disease_names() -> list[str]:
    """
    Fetch unique disease/condition names from PostgreSQL.
    Uses diseases table if populated, otherwise falls back to
    medical_condition from drugs_side_effects.
    """
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM diseases")
    count = cur.fetchone()[0]

    if count > 0:
        cur.execute("SELECT name FROM diseases ORDER BY name")
    else:
        print("[INFO] Table 'diseases' is empty; using 'drugs_side_effects.medical_condition'")
        cur.execute("SELECT DISTINCT medical_condition FROM drugs_side_effects WHERE medical_condition IS NOT NULL ORDER BY medical_condition")

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [row[0] for row in rows]


def fetch_medlineplus(disease_name: str) -> dict | None:
    """
    Query MedlinePlus API for a given disease name.
    Extracts FullSummary and relevant metadata from the XML response.
    Returns a dict or None if not found.
    """
    params = {"db": "healthTopics", "term": disease_name}
    try:
        resp = requests.get(MEDLINE_BASE_URL, params=params, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  [WARN] Error calling API for '{disease_name}': {e}")
        return None

    # The response is XML
    try:
        root = ET.fromstring(resp.content)
    except ET.ParseError as e:
        print(f"  [WARN] Error parsing XML for '{disease_name}': {e}")
        return None

    # MedlinePlus namespace
    ns = {"nlm": "https://wsearch.nlm.nih.gov/ws/query"}

    # First result
    doc = root.find(".//nlm:document", ns)
    if doc is None:
        # Try without namespace (fallback)
        doc = root.find(".//document")
    if doc is None:
        print(f"  [INFO] No results for '{disease_name}'")
        return None

    def get_content(tag):
        # Try with and without namespace
        el = doc.find(f"nlm:content[@name='{tag}']", ns)
        if el is None:
            el = doc.find(f"content[@name='{tag}']")
        return el.text.strip() if el is not None and el.text else None

    full_summary = get_content("FullSummary")
    if not full_summary:
        print(f"  [INFO] Empty FullSummary for '{disease_name}'")
        return None

    return {
        "disease_name": disease_name,
        "title": get_content("title"),
        "full_summary": full_summary,
        "url": doc.attrib.get("url"),
        "source": "MedlinePlus",
    }


def ingest_medlineplus(skip_connection_check: bool = False):
    """
    Fetch MedlinePlus summaries for every disease in PostgreSQL and store them
    in MongoDB.

    The function is incremental: diseases that already have a document in the
    ``medlineplus_health_topics`` collection are skipped rather than
    overwritten, so the script can be interrupted and re-run without losing
    progress or creating duplicates.

    Parameters
    ----------
    skip_connection_check : bool
        When True, skip the MongoDB ping check (useful in tests or when the
        caller has already verified connectivity).

    Returns
    -------
    dict
        Summary counts: ``{"ingested": int, "skipped": int, "failed": int}``.
    """
    db = get_mongo_db()

    if not skip_connection_check:
        ok, msg = verify_mongo_connection(db)
        if not ok:
            print("ERROR:", msg, file=sys.stderr)
            sys.exit(1)
        print("[DEBUG] DB connection verified.")

    # 1. Fetch disease names from PostgreSQL
    disease_names = fetch_disease_names()
    print(f"Diseases found in PostgreSQL: {len(disease_names)}")

    collection = db[COLLECTION_NAME]

    ingested, skipped, failed = 0, 0, 0

    for disease in disease_names:
        print(f"Processing: {disease}")

        # Avoid duplicates; only insert if the entry doesn't exist
        existing = collection.find_one({"disease_name": disease})
        if existing:
            print(f"  [SKIP] Entry already exists for '{disease}'")
            skipped += 1
            continue

        data = fetch_medlineplus(disease)
        if data:
            collection.insert_one(data)
            ingested += 1
        else:
            failed += 1

    print(f"\nIngestion completed: {ingested} inserted | {skipped} ignored | {failed} no results")
    return {"ingested": ingested, "skipped": skipped, "failed": failed}


if __name__ == "__main__":
    ok, msg = verify_mongo_connection()
    print("[DEBUG]", msg)
    if not ok:
        print("Aborting: fix the connection and run again.", file=sys.stderr)
        sys.exit(1)
    ingest_medlineplus()
