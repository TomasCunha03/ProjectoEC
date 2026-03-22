import os

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from psycopg2.extras import execute_values

from chat_saude.infrastructure.database.db_connection import get_db_connection

load_dotenv()


def ingest_brfss(csv_path):
    if not os.path.exists(csv_path):
        print(f"Error: File {csv_path} was not found.")
        return

    print("Loading BRFSS dataset... (this may take a while depending on size)")
    df = pd.read_csv(csv_path, low_memory=False)

    cols_map = {
        "_state": "state_code",
        "seqno": "sequence_no",
        # Diagnoses (diseases)
        "diabete4": "diagnosed_diabetes",
        "asthma3": "diagnosed_asthma",
        "asthnow": "asthma_now",
        "cvdstrk3": "diagnosed_stroke",
        "cvdinfr4": "diagnosed_heart_attack",
        "cvdcrhd4": "diagnosed_heart_dis",
        "chccopd3": "diagnosed_copd",
        "addepev3": "diagnosed_depressive",
        "chckdny2": "diagnosed_kidney_dis",
        "havarth4": "diagnosed_arthritis",
        "chcscnc1": "diagnosed_skin_cancer",
        "chcocnc1": "diagnosed_other_cancer",
        # Risk factors and prevention
        "bphigh6": "high_blood_pressure",
        "toldhi3": "high_cholesterol",
        "smoke100": "smoke_100",
        "_rfbing6": "alcohol_binge",
        "exerany2": "exercise_any",
        # Diabetes screening
        "pdiabts1": "last_glucose_test",
        # "chkhemo3": "hba1c_check_freq",
        # Self-assessment and biometrics
        "genhlth": "general_health",
        "physhlth": "physical_health_days",
        "menthlth": "mental_health_days",
        "wtkg3": "weight_kg",
        "htm4": "height_cm",
        "_bmi5": "bmi",
    }

    available_cols = [c for c in cols_map.keys() if c in df.columns]
    df_final = df[available_cols].rename(columns=cols_map)
    print(f"Mapped columns: {len(df_final.columns)} out of {len(cols_map)}")

    # Cleaning and transformation
    if "bmi" in df_final.columns:
        df_final["bmi"] = pd.to_numeric(df_final["bmi"], errors="coerce") / 100
    if "weight_kg" in df_final.columns:
        df_final["weight_kg"] = pd.to_numeric(df_final["weight_kg"], errors="coerce") / 100

    for col in df_final.columns:
        if col not in ["bmi", "weight_kg"]:
            df_final[col] = pd.to_numeric(df_final[col], errors="coerce")

    df_final = df_final.replace({np.nan: None})

    # Insert
    conn = get_db_connection()
    cur = conn.cursor()

    columns = list(df_final.columns)
    insert_query = f"""
        INSERT INTO brfss_responses ({", ".join(columns)})
        VALUES %s
        ON CONFLICT (sequence_no) DO NOTHING
    """

    data_tuples = [tuple(x) for x in df_final.to_numpy()]

    try:
        execute_values(cur, insert_query, data_tuples)
        conn.commit()
        print(f"Success! Processed {len(df_final)} records into table brfss_responses.")
    except Exception as e:
        conn.rollback()
        print(f"Error during ingestion: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    path = "/app/data/BRFSS2023.csv"
    ingest_brfss(path)
