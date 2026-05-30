"""
MongoDB client factory for the chat_saude infrastructure layer.

Provides a single entry point for obtaining a pymongo MongoClient
configured from the application's centralized settings object.
Use get_mongo_client() to obtain a client, then select a database and
collection from it as needed by the calling service.
"""

from pymongo import MongoClient

from chat_saude.config.settings import settings


def get_mongo_client():
    """Build and return a pymongo MongoClient using centralized settings.

    The client connects to the host and port defined in the application
    settings (typically sourced from environment variables or a .env file).
    Authentication is not applied here; if required it should be configured
    in the settings object or passed by the caller after obtaining the client.

    Returns:
        pymongo.MongoClient: An unauthenticated MongoClient connected to the
        configured host and port.
    """
    return MongoClient(host=settings.MONGO_HOST, port=settings.MONGO_PORT)
