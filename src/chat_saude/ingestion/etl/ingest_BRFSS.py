import os

import numpy as np
import pandas as pd
from chat_saude.infrastructure.database.db_connection import get_db_connection
from dotenv import load_dotenv
from psycopg2.extras import execute_values

load_dotenv()


def ingest_brfss(csv_path):
    if not os.path.exists(csv_path):
        print(f"Erro: O ficheiro {csv_path} não foi encontrado.")
        return

    print("A carregar dataset BRFSS... (isto pode demorar dependendo do tamanho)")
    df = pd.read_csv(csv_path, low_memory=False)

    cols_map = {
        "_state": "state_code",
        "seqno": "sequence_no",
        # Diagnósticos (Doenças)
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
        # Fatores de Risco e Prevenção
        "bphigh6": "high_blood_pressure",
        "toldhi3": "high_cholesterol",
        "smoke100": "smoke_100",
        "_rfbing6": "alcohol_binge",
        "exerany2": "exercise_any",
        # Rastreio de Diabetes
        "pdiabts1": "last_glucose_test",
        "chkhemo3": "hba1c_check_freq",
        # Auto-avaliação e Biometria
        "genhlth": "general_health",
        "physhlth": "physical_health_days",
        "menthlth": "mental_health_days",
        "wtkg3": "weight_kg",
        "htm4": "height_cm",
        "_bmi5": "bmi",
    }

    available_cols = [c for c in cols_map.keys() if c in df.columns]
    df_final = df[available_cols].rename(columns=cols_map)
    print(f"Campos mapeados: {len(df_final.columns)} de {len(cols_map)}")

    # Limpeza e Transformação
    if "bmi" in df_final.columns:
        df_final["bmi"] = pd.to_numeric(df_final["bmi"], errors="coerce") / 100
    if "weight_kg" in df_final.columns:
        df_final["weight_kg"] = pd.to_numeric(df_final["weight_kg"], errors="coerce") / 100

    for col in df_final.columns:
        if col not in ["bmi", "weight_kg"]:
            df_final[col] = pd.to_numeric(df_final[col], errors="coerce")

    df_final = df_final.replace({np.nan: None})

    # Inserção
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
        print(f"Sucesso! {len(df_final)} registos processados na tabela brfss_responses.")
    except Exception as e:
        conn.rollback()
        print(f"Erro na ingestão: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "BRFSS2023.csv"
    ingest_brfss(path)
