"""
Home Remedies PDF ingestion into ChromaDB.

Fetches the PDF from URL, extracts text, splits into chunks,
generates embeddings and stores in a dedicated ChromaDB collection.
The collection is recreated from scratch on every run so that updates
to the source document are always reflected cleanly.
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
CHUNK_SIZE = 500  # characters per chunk
CHUNK_OVERLAP = 50  # overlap between chunks — keeps context across chunk boundaries

# Shared embedding model; loaded once at module level to avoid repeated initialisation
embedding_model = SentenceTransformer("BAAI/bge-base-en-v1.5")

# ChromaDB client — host/port resolved from environment so the same code works
# both locally and inside Docker Compose
client_chromadb = chromadb.HttpClient(host=os.getenv("VECTOR_HOST", "db_vector"), port=int(os.getenv("VECTOR_PORT", "8010")))


def extract_text(url: str) -> str:
    """Download a PDF from *url* and return its full text content.

    Each page's text is concatenated with a newline separator.  Pages that
    yield no text (e.g. image-only pages) are silently skipped.

    Args:
        url: Public URL of the PDF to download.

    Returns:
        The extracted plain text from all readable pages.

    Raises:
        requests.HTTPError: If the HTTP response status indicates an error.
    """
    print(f"Downloading PDF: {url}")
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    reader = PdfReader(io.BytesIO(resp.content))
    text = ""
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text += page_text + "\n"
    return text


def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split *text* into overlapping fixed-size character chunks.

    Args:
        text: The full document text to split.
        chunk_size: Maximum number of characters per chunk.
        overlap: Number of characters shared between consecutive chunks.

    Returns:
        A list of non-empty chunk strings.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end].strip())
        start += chunk_size - overlap
    return [c for c in chunks if c]  # remove empty chunks produced by trailing whitespace


def ingest_home_remedies():
    """Run the full ingestion pipeline for the home remedies PDF.

    Steps:
        1. Download and extract text from the PDF.
        2. Split the text into overlapping chunks.
        3. Generate normalised embeddings for each chunk.
        4. Wipe the existing ChromaDB collection (if present) and insert all chunks.
    """
    # 1. Extraction
    text = extract_text(PDF_URL)
    print(f"Extracted text: {len(text)} characters")

    # 2. Chunking
    chunks = split_into_chunks(text)
    print(f"Generated chunks: {len(chunks)}")

    # 3. Embeddings — normalise so cosine similarity equals dot product
    print("Generating embeddings...")
    embeddings = embedding_model.encode(chunks, normalize_embeddings=True).tolist()

    # 4. Insert into ChromaDB — drop first to guarantee a clean re-ingest
    collections = client_chromadb.list_collections()
    names = [c.name for c in collections]

    if COLLECTION_NAME in names:
        client_chromadb.delete_collection(COLLECTION_NAME)
    collection = client_chromadb.get_or_create_collection(name=COLLECTION_NAME)

    # Use random UUIDs as chunk IDs; chunk_index in metadata allows ordering later
    ids = [str(uuid.uuid4()) for _ in chunks]
    metadatas = [{"source": PDF_URL, "chunk_index": i} for i in range(len(chunks))]

    collection.add(
        ids=ids,
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    print(f"Success! {len(chunks)} chunks inserted into collection '{COLLECTION_NAME}'.")


if __name__ == "__main__":
    ingest_home_remedies()
