"""
Manual ChromaDB inspection script.

Connects to a local ChromaDB instance and prints the available collections
and the document count in the target collection. Useful for quick sanity
checks during development without running the full ingestion pipeline.
"""

import chromadb

COLLECTION_NAME = "pmc_medicine_preventive"

# Connect to a locally running ChromaDB instance (dev / manual-testing port)
client = chromadb.HttpClient(host="localhost", port=8002)
collection = client.get_or_create_collection(name=COLLECTION_NAME)

print(client.list_collections())  # List collections
print(collection.count())  # Show how many documents are stored in the collection
