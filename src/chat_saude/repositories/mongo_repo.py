"""
MongoDB repository abstraction for chat_saude.

Wraps the shared MongoClient (managed by the infrastructure layer) so that
application code does not need to deal with client lifecycle or connection
management directly.
"""

from chat_saude.infrastructure.database.mongo import get_mongo_client


class MongoRepository:
    """Repository for MongoDB data access using the shared client.

    A new instance selects a specific database by name.  The underlying
    MongoClient is reused from the infrastructure layer so connections are
    pooled across all repository instances.
    """

    def __init__(self, db_name: str):
        """
        Args:
            db_name: The MongoDB database to operate on.
        """
        client = get_mongo_client()
        self.db = client[db_name]

    def find(self, collection: str, query: dict):
        """Return a list of documents from the collection matching the query.

        Args:
            collection: Name of the MongoDB collection to search.
            query: A pymongo filter document (e.g. {"status": "active"}).

        Returns:
            A list of BSON documents with the ``_id`` field still present.
        """
        return list(self.db[collection].find(query))
