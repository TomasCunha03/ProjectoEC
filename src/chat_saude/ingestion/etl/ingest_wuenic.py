import os

import numpy as np
import pandas as pd
from chat_saude.infrastructure.database.db_connection import get_db_connection
from dotenv import load_dotenv
from psycopg2.extras import execute_values

load_dotenv()


def ingest_wuenic(file_path):
    if not os.path.exists(file_path):
        print(f"Erro: O ficheiro {file_path} não foi encontrado.")
        return

    print("A carregar dataset WUENIC...")
    df = pd.read_excel(file_path, sheet_name="wuenic_master")

    # Normalizar nomes
    df = df.rename(columns={
        "Country": "country",
        "ISOCountryCode": "iso_code",
        "Vaccine": "vaccine",
        "Year": "year",
        "WUENIC": "wuenic_coverage",
        "AdministrativeCoverage": "administrative_coverage",
        "ChildrenVaccinated": "children_vaccinated",
        "ChildrenInTarget": "children_target",
        "BirthsUNPD": "births_unpd",
        "SurvivingInfantsUNPD": "surviving_infants"
    })

    df = df.replace({np.nan: None})

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # -------------------------
        # 1. COUNTRY DIM
        # -------------------------
        country_df = df[["iso_code", "country"]].drop_duplicates()

        execute_values(
            cur,
            """
            INSERT INTO country_dim (iso_code, country_name)
            VALUES %s
            ON CONFLICT (iso_code) DO NOTHING
            """,
            [tuple(x) for x in country_df.to_numpy()]
        )

        # -------------------------
        # 2. VACCINE DIM
        # -------------------------
        vaccine_df = df[["vaccine"]].drop_duplicates()

        execute_values(
            cur,
            """
            INSERT INTO vaccine_dim (vaccine_code)
            VALUES %s
            ON CONFLICT (vaccine_code) DO NOTHING
            """,
            [tuple(x) for x in vaccine_df.to_numpy()]
        )

        # -------------------------
        # 3. OBTER IDS
        # -------------------------
        cur.execute("SELECT id, iso_code FROM country_dim")
        country_map = dict(cur.fetchall())

        cur.execute("SELECT id, vaccine_code FROM vaccine_dim")
        vaccine_map = dict(cur.fetchall())

        # -------------------------
        # 4. FACT TABLE
        # -------------------------
        fact_data = []

        for _, row in df.iterrows():
            country_id = country_map.get(row["iso_code"])
            vaccine_id = vaccine_map.get(row["vaccine"])

            fact_data.append((
                country_id,
                vaccine_id,
                row.get("year"),
                row.get("wuenic_coverage"),
                row.get("administrative_coverage"),
                row.get("children_vaccinated"),
                row.get("children_target"),
                row.get("births_unpd"),
                row.get("surviving_infants"),
                None,  # calculated_coverage
                False  # anomaly_flag
            ))

        execute_values(
            cur,
            """
            INSERT INTO immunization_fact (
                country_id,
                vaccine_id,
                year,
                wuenic_coverage,
                administrative_coverage,
                children_vaccinated,
                children_target,
                births_unpd,
                surviving_infants,
                calculated_coverage,
                anomaly_flag
            )
            VALUES %s
            ON CONFLICT (country_id, vaccine_id, year) DO NOTHING
            """,
            fact_data
        )

        conn.commit()
        print(f"Sucesso! {len(fact_data)} registos inseridos na immunization_fact.")

    except Exception as e:
        conn.rollback()
        print(f"Erro na ingestão: {e}")

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "wuenic-input.xlsx"
    ingest_wuenic(path)