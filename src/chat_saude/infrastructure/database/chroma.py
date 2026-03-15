import chromadb

from chat_saude.config.settings import settings


def get_chroma_client():
    """Build and return a ChromaDB HTTP client using centralized settings."""
    return chromadb.HttpClient(
        host=settings.VECTOR_DB_HOST,
        port=settings.VECTOR_DB_PORT,
    )
