from chat_saude.infrastructure.database.mongo import get_mongo_client


class MongoRepository:
    """Repository for MongoDB data access using the shared client."""

    def __init__(self, db_name: str):
        client = get_mongo_client()
        self.db = client[db_name]

    def find(self, collection: str, query: dict):
        """Return a list of documents from the collection matching the query."""
        return list(self.db[collection].find(query))
