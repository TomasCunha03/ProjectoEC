import chromadb

COLLECTION_NAME = "pmc_medicine_preventive"
client = chromadb.HttpClient(host="localhost", port=8002)
collection = client.get_or_create_collection(name=COLLECTION_NAME)
print(client.list_collections())  # List collections
print(collection.count())
