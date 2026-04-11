import subprocess

scripts = [
    "src/chat_saude/ingestion/etl/ingest_global_health.py",
    "src/chat_saude/ingestion/etl/ingest_CDI.py",
    "src/chat_saude/ingestion/etl/ingest_BRFSS.py",
    "src/chat_saude/ingestion/etl/ingest_drugs.py",
    "src/chat_saude/ingestion/etl/ingest_wuenic.py",
    "src/chat_saude/ingestion/etl/ingest_symptoms.py",
    "src/chat_saude/ingestion/api/medlineplus.py",
    "src/chat_saude/ingestion/api/gho.py",
    "src/chat_saude/ingestion/crawlers/home_remedies_ingest.py",
    "src/chat_saude/ingestion/crawlers/chromadb_ingest.py",
]

for script in scripts:
    print(f"A correr {script}...")
    subprocess.run(["python", script], check=True)
