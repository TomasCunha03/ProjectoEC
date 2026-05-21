"""
Interactive CLI to test the MongoDB tool pipeline.

Runs a series of automated smoke tests against the MongoDB connection
(connection ping, indicator search, dimension lookup) and then drops into
an interactive prompt where free-text questions are routed through the full
LLM + MongoDB pipeline.

Run from repo root with PYTHONPATH=src: python scripts/mongo_tool_terminal.py
"""

from chat_saude.tools.mongo_tool import (
    _get_dimension_values,
    _get_mongo_db,
    _list_collections,
    _search_indicators,
    mongo_query,
)


def test_connection(db):
    """Verify that the MongoDB server is reachable and list available collections.

    Args:
        db: A pymongo Database object returned by _get_mongo_db().

    Returns:
        True if the ping succeeded, False otherwise.
    """
    print("\n[1] Testing MongoDB connection...")
    try:
        db.client.admin.command("ping")
        collections = _list_collections(db)
        print(f"    OK - {len(collections)} collections found:")
        for c in collections:
            print(f"       - {c}")
    except Exception as e:
        print(f"    ERROR: {e}")
        return False
    return True


def test_search_indicators(db):
    """Search for health indicators matching a fixed keyword and print the top results.

    Args:
        db: A pymongo Database object returned by _get_mongo_db().
    """
    keyword = "diabetes"
    print(f"\n[2] Searching indicators for '{keyword}'...")
    results = _search_indicators(db, keyword, limit=5)
    if results:
        print(f"    OK - {len(results)} results:")
        for r in results:
            print(f"       [{r.get('IndicatorCode', 'N/A')}] {r.get('IndicatorName', 'N/A')}")
    else:
        # Empty result usually means the GHO ingestion has not been run yet
        print("    No results (empty database? run api ingestion first).")


def test_dimension_values(db):
    """Retrieve a sample of values for the COUNTRY dimension and print them.

    Args:
        db: A pymongo Database object returned by _get_mongo_db().
    """
    dim = "COUNTRY"
    print(f"\n[3] Getting values for dimension '{dim}'...")
    results = _get_dimension_values(db, dim, limit=5)
    if results:
        print(f"    OK - first {len(results)} countries:")
        for r in results:
            print(f"       [{r.get('Code', 'N/A')}] {r.get('Title', 'N/A')}")
    else:
        print("    No results for this dimension.")


def interactive_mode():
    """Start an interactive prompt that forwards questions to the mongo_query pipeline.

    Accepts Portuguese ("sair") and English ("exit", "quit", "q") exit commands.
    Ctrl+C is also handled gracefully.
    """
    print("\n" + "=" * 80)
    print("INTERACTIVE MODE - MONGODB TOOL")
    print("=" * 80)
    print("Type a question to test the full pipeline (LLM + MongoDB)")
    print("Commands: use 'exit' to quit.\n")

    while True:
        try:
            question = input("Question: ").strip()
            if not question:
                continue
            if question.lower() in ["sair", "exit", "quit", "q"]:
                print("Exiting...")
                break

            print("Processing...")
            result = mongo_query(question)
            print(f"\nAnswer:\n{result}")
            print("-" * 80)

        except KeyboardInterrupt:
            print("\nInterrupted. Bye!")
            break
        except Exception as e:
            print(f"Error: {e}")
            print("-" * 80)


if __name__ == "__main__":
    db = _get_mongo_db()

    # Run smoke tests first; only enter interactive mode if the connection is healthy
    ok = test_connection(db)
    if ok:
        test_search_indicators(db)
        test_dimension_values(db)

    interactive_mode()
