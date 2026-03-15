import json
import os

import chromadb
from sentence_transformers import SentenceTransformer

# Ficheiros
DATA_DIR = "../../data"
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


# Coleção e embedding
COLLECTION_NAME = "pmc_medicine_preventive"
embbeding_model = SentenceTransformer("BAAI/bge-base-en-v1.5")

# Ligação ao ChromaDB
client = chromadb.HttpClient(host="localhost", port=8002)
print(client.list_collections())  # Lista coleções

if COLLECTION_NAME in [c.name for c in client.list_collections()]:
    client.delete_collection(COLLECTION_NAME)

collection = client.get_or_create_collection(name=COLLECTION_NAME)


# Carregar Ficheiros
all_articles = []
for file in JSON_FILES:
    path = os.path.join(DATA_DIR, file)

    if not os.path.exists(path):
        print(f"File not found:{path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        all_articles.extend(data)

print(f"Loaded {len(all_articles)} total articles")


# Preparar para guardar no ChromaDB
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

# Criar embeddings
embbeding = embbeding_model.encode(documents, normalize_embeddings=True, show_progress_bar=True)

# Armazenar no Chromadb
collection.add(documents=documents, embeddings=embbeding, metadatas=metadatas, ids=ids)

print("Stored in ChromaDB Successfully!")
