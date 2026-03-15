from pymongo import MongoClient

from chat_saude.config.settings import settings


def get_mongo_client():
    """Build and return a pymongo MongoClient using centralized settings."""
    return MongoClient(host=settings.MONGO_HOST, port=settings.MONGO_PORT)
