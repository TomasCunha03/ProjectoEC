import pandas as pd
from dotenv import load_dotenv

from chat_saude.infrastructure.database.db_connection import get_db_connection

# Load environment variables
load_dotenv()


def ingest_data():
    conn = get_db_connection()
    cur = conn.cursor()

    # 1. Load CSVs
    df_desc = pd.read_csv("/app/data/symptom_Description.csv")
    df_prec = pd.read_csv("/app/data/symptom_precaution.csv")
    df_sev = pd.read_csv("/app/data/Symptom-severity.csv")
    df_mapping = pd.read_csv("/app/data/dataset.csv")

    # 2. Ingest Diseases and Descriptions
    for _, row in df_desc.iterrows():
        cur.execute(
            """
                INSERT INTO diseases (name, description)
                VALUES (%s, %s) 
                ON CONFLICT (name) DO NOTHING
                """,
            (row["Disease"].strip(), row["Description"]),
        )

    # 3. Ingest Symptoms and Severities
    for _, row in df_sev.iterrows():
        cur.execute(
            """
                INSERT INTO symptoms (name, severity_weight)
                VALUES (%s, %s) 
                ON CONFLICT (name) DO NOTHING
                """,
            (row["Symptom"].strip().replace("_", " "), row["weight"]),
        )

    # 4. Ingest Disease-Symptom Mappings
    # We unpivot the 17 symptom columns into a clean list
    for _, row in df_mapping.iterrows():
        disease_name = row["Disease"].strip()
        # Get disease_id
        cur.execute("SELECT disease_id FROM diseases WHERE name = %s", (disease_name,))
        res = cur.fetchone()
        if res:
            disease_id = res[0]
            # Loop through symptom columns (Symptom_1 to Symptom_17)
            for i in range(1, 18):
                s_name = row[f"Symptom_{i}"]
                if pd.notna(s_name):
                    s_name = s_name.strip().replace("_", " ")
                    # Ensure symptom exists and get ID
                    cur.execute("SELECT symptom_id FROM symptoms WHERE name = %s", (s_name,))
                    s_res = cur.fetchone()
                    if s_res:
                        cur.execute(
                            (
                                "INSERT INTO disease_symptoms (disease_id, symptom_id) "
                                "VALUES (%s, %s) "
                                "ON CONFLICT DO NOTHING"
                            ),
                            (disease_id, s_res[0]),
                        )

    # 5. Ingest Precautions
    for _, row in df_prec.iterrows():
        cur.execute("SELECT disease_id FROM diseases WHERE name = %s", (row["Disease"].strip(),))
        res = cur.fetchone()
        if res:
            d_id = res[0]
            for i in range(1, 5):
                prec = row[f"Precaution_{i}"]
                if pd.notna(prec):
                    cur.execute(
                        "INSERT INTO disease_precautions (disease_id, precaution) VALUES (%s, %s)",
                        (d_id, prec),
                    )

    conn.commit()
    cur.close()
    conn.close()
    print("Ingestion completed successfully!")


if __name__ == "__main__":
    ingest_data()
