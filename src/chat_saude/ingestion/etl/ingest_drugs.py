import os

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from psycopg2.extras import execute_values

from chat_saude.infrastructure.database.db_connection import get_db_connection

load_dotenv()


def ingest_drugs(csv_path):
    if not os.path.exists(csv_path):
        print(f"Error: File {csv_path} was not found.")
        return

    print("Loading dataset Drugs & Side Effects...")
    df = pd.read_csv(csv_path)

    cols_map = {
        "drug_name": "drug_name",
        "medical_condition": "medical_condition",
        "side_effects": "side_effects",
        "generic_name": "generic_name",
        "drug_classes": "drug_classes",
        "brand_names": "brand_names",
        "activity": "activity",
        "rx_otc": "rx_otc",
        "pregnancy_category": "pregnancy_category",
        "csa": "csa",
        "alcohol": "alcohol",
        "related_drugs": "related_drugs",
        "medical_condition_description": "medical_condition_description",
        "rating": "rating",
        "no_of_reviews": "no_of_reviews",
        "drug_link": "drug_link",
        "medical_condition_url": "medical_condition_url",
    }

    # Keep only columns that exist in the CSV (protection against variations)
    available = {k: v for k, v in cols_map.items() if k in df.columns}
    df = df[list(available.keys())].rename(columns=available)
    print(f"Mapped columns: {len(df.columns)} of {len(cols_map)}")

    # Cleaning
    if "rating" in df.columns:
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
    if "no_of_reviews" in df.columns:
        df["no_of_reviews"] = pd.to_numeric(df["no_of_reviews"], errors="coerce").astype("Int64")

    df = df.replace({np.nan: None})

    # Insert
    conn = get_db_connection()
    cur = conn.cursor()

    columns = list(df.columns)
    insert_query = f"""
        INSERT INTO drugs_side_effects ({", ".join(columns)})
        VALUES %s
        ON CONFLICT (drug_name, medical_condition) DO NOTHING
    """

    data_tuples = [tuple(x) for x in df.to_numpy()]

    try:
        execute_values(cur, insert_query, data_tuples)
        conn.commit()
        print(f"Success! Inserted {len(df)} records into table drugs_side_effects.")
    except Exception as e:
        conn.rollback()
        print(f"Error during ingestion: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    path = "/app/data/drugs_side_effects.csv"
    ingest_drugs(path)
