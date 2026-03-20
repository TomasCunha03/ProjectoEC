from chat_saude.infrastructure.database.chroma import get_chroma_client


class VectorRepository:
    """Repository for vector store (Chroma) access using the shared client."""

    def __init__(self, collection_name: str):
        client = get_chroma_client()
        self.collection = client.get_or_create_collection(name=collection_name)

    def query(self, query_embeddings, n_results: int = 5):
        """Query the collection by embeddings and return results."""
        return self.collection.query(
            query_embeddings=query_embeddings,
            n_results=n_results,
        )
