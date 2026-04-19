import json
import os
import sys

import chromadb
from sentence_transformers import SentenceTransformer

# Allow `python src/.../chromadb_ingest.py` and Docker `PYTHONPATH=/app/src`
_REPO_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if _REPO_SRC not in sys.path:
    sys.path.insert(0, _REPO_SRC)

from chat_saude.config.settings import settings

# Files
DATA_DIR = "/app/data"
JSON_FILES = ["pmc_simples.json", "pmc_preventive_medicine_clean.json"]


# Chunking
def chunk_text(text, size=800, overlap=200):
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


# Collection and embedding model
COLLECTION_NAME = "pmc_medicine_preventive"
embbeding_model = SentenceTransformer("BAAI/bge-base-en-v1.5")

# Connection to ChromaDB (same host/port as RAG runtime: settings / VECTOR_DB_*)
client = chromadb.HttpClient(host=settings.VECTOR_DB_HOST, port=settings.VECTOR_DB_PORT)
print(client.list_collections())  # List collections

if COLLECTION_NAME in [c.name for c in client.list_collections()]:
    client.delete_collection(COLLECTION_NAME)

collection = client.get_or_create_collection(name=COLLECTION_NAME)


# Load files
all_articles = []
for file in JSON_FILES:
    path = os.path.join(DATA_DIR, file)

    if not os.path.exists(path):
        print(f"File not found:{path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        all_articles.extend(data)

print(f"Loaded {len(all_articles)} total articles")


# Prepare documents to store in ChromaDB
documents = []
metadatas = []
ids = []

doc_id = 0
for article in all_articles:
    text = article.get("text", "").strip()
    if not text:
        continue

    chunks = chunk_text(text)

    for chunk in chunks:
        documents.append(chunk)

        metadatas.append(
            {
                "title": article.get("title"),
                "source_url": article.get("source_url"),
                "keyword": str(article.get("keyword") or article.get("mesh_query") or ""),
            }
        )

        ids.append(f"pmc_{doc_id}")
        doc_id += 1

print(f"Prepared {len(documents)} chunks")

# Create embeddings
embbeding = embbeding_model.encode(documents, normalize_embeddings=True, show_progress_bar=True)

# Store in Chroma
collection.add(documents=documents, embeddings=embbeding, metadatas=metadatas, ids=ids)

print("Stored in ChromaDB Successfully!")
