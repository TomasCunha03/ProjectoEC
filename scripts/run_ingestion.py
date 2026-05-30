"""
Master ingestion runner.

Executes every ingestion script in the defined order using the same Python
interpreter that is running this file.  If any script exits with a non-zero
return code, ``subprocess.run`` raises CalledProcessError and the pipeline
stops immediately, preventing downstream scripts from operating on incomplete
data.

Run from the repo root (where src/ is visible) so that the child scripts can
resolve their own relative imports correctly.
"""

import subprocess

# Scripts are ordered so that ETL jobs (raw data → MongoDB) run before the
# crawler-based ChromaDB ingestion, which depends on data already being present
scripts = [
    "src/chat_saude/ingestion/etl/ingest_BRFSS.py",
    "src/chat_saude/ingestion/etl/ingest_drugs.py",
    "src/chat_saude/ingestion/etl/ingest_wuenic.py",
    "src/chat_saude/ingestion/etl/ingest_symptoms.py",
    "src/chat_saude/ingestion/api/medlineplus.py",
    "src/chat_saude/ingestion/api/gho.py",
    "src/chat_saude/ingestion/crawlers/home_remedies_ingest.py",
    "src/chat_saude/ingestion/crawlers/chromadb_ingest.py",
    "src/chat_saude/ingestion/etl/ingest_global_health.py",
    "src/chat_saude/ingestion/etl/ingest_CDI.py",
]

for script in scripts:
    print(f"A correr {script}...")
    # check=True ensures a failing script aborts the whole pipeline
    subprocess.run(["python", script], check=True)
