"""
Home Remedies PDF ingestion into ChromaDB.
Fetches the PDF from URL, extracts text, splits into chunks,
generates embeddings and stores in a dedicated ChromaDB collection.
"""

import io
import os
import uuid

import chromadb
import requests
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer

PDF_URL = "https://www.columbia.edu/itc/hs/medical/residency/peds/new_compeds_site/pdfs_new/quick_guideto_homeremedies2-20-08.pdf"
COLLECTION_NAME = "home_remedies"
CHUNK_SIZE = 500  # caracteres por chunk
CHUNK_OVERLAP = 50  # sobreposição entre chunks

embedding_model = SentenceTransformer("BAAI/bge-base-en-v1.5")
client_chromadb = chromadb.HttpClient(
    host=os.getenv("VECTOR_HOST", "db_vector"), port=int(os.getenv("VECTOR_PORT", "8002"))
)


def extract_text(url: str) -> str:
    """Download PDF and extract text."""
    print(f"A fazer download do PDF: {url}")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    reader = PdfReader(io.BytesIO(resp.content))
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text


def split_into_chunks(
    text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start += chunk_size - overlap
    return [c for c in chunks if c]  # remover chunks vazios


def ingest_home_remedies():
    # 1. Extração
    text = extract_text(PDF_URL)
    print(f"Texto extraído: {len(text)} caracteres")

    # 2. Chunking
    chunks = split_into_chunks(text)
    print(f"Chunks gerados: {len(chunks)}")

    # 3. Embeddings
    print("A gerar embeddings...")
    embeddings = embedding_model.encode(chunks, normalize_embeddings=True).tolist()

    # 4. Inserção no ChromaDB
    collection = client_chromadb.get_or_create_collection(name=COLLECTION_NAME)

    ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [{"source": PDF_URL, "chunk_index": i} for i in range(len(chunks))]

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    print(f"Sucesso! {len(chunks)} chunks inseridos na coleção '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    ingest_home_remedies()
