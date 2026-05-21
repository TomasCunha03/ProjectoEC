"""
Chroma vector-store repository abstraction for chat_saude.

Wraps the shared ChromaDB client (managed by the infrastructure layer) to
expose a minimal interface for similarity search.  Collection creation is
handled lazily via get_or_create_collection so callers do not need to worry
about whether the collection already exists.
"""

from chat_saude.infrastructure.database.chroma import get_chroma_client


class VectorRepository:
    """Repository for vector store (Chroma) access using the shared client.

    Each instance is bound to a single named collection.  The collection is
    created automatically if it does not exist yet, which simplifies first-run
    setup.
    """

    def __init__(self, collection_name: str):
        """
        Args:
            collection_name: Name of the Chroma collection to use or create.
        """
        client = get_chroma_client()
        # get_or_create_collection is idempotent: safe to call on every startup.
        self.collection = client.get_or_create_collection(name=collection_name)

    def query(self, query_embeddings, n_results: int = 5):
        """Query the collection by embeddings and return the nearest neighbours.

        Args:
            query_embeddings: A list of embedding vectors to search with.
                              Shape: [[float, ...], ...] (one list per query).
            n_results: Maximum number of results to return per query vector.

        Returns:
            A Chroma query result dict containing ``ids``, ``distances``,
            ``documents``, and ``metadatas`` keys.
        """
        return self.collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results,
        )
