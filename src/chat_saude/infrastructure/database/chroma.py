"""
ChromaDB client factory for the chat_saude infrastructure layer.

Provides a single entry point for obtaining a ChromaDB HTTP client
configured from the application's centralized settings object.
"""

import chromadb

from chat_saude.config.settings import settings


def get_chroma_client():
    """Build and return a ChromaDB HTTP client using centralized settings.

    Connects to the vector database over HTTP using the host and port
    defined in the application settings (typically sourced from environment
    variables or a .env file).

    Returns:
        chromadb.HttpClient: A connected ChromaDB client ready for collection
        operations such as querying and inserting embeddings.
    """
    return chromadb.HttpClient(
        host=settings.VECTOR_DB_HOST,
        port=settings.VECTOR_DB_PORT,
    )
