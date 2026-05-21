"""
ETL pipeline for the WHO/UNICEF Estimates of National Immunization Coverage
(WUENIC) dataset.

WUENIC provides annual country-level vaccination coverage estimates for
childhood immunisation programmes.  The data is organised as a star schema:

* ``country_dim``        -- dimension table of ISO country codes and names
* ``vaccine_dim``        -- dimension table of vaccine codes
* ``immunization_fact``  -- fact table linking countries, vaccines, and years
                            with coverage and population figures

The Excel workbook is read from the ``wuenic_master`` sheet.  Dimension tables
are populated first so that surrogate keys are available when building the fact
rows.
"""

import os

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from psycopg2.extras import execute_values

from chat_saude.infrastructure.database.db_connection import get_db_connection

load_dotenv()


def ingest_wuenic(file_path):
    """
    Load the WUENIC Excel workbook and ingest it into the star-schema tables.

    The function is idempotent: all INSERT statements use
    ON CONFLICT … DO NOTHING, so re-running will not create duplicate rows.

    Parameters
    ----------
    file_path : str
        Absolute path to the WUENIC Excel file (e.g. ``wuenic-input.xlsx``).
    """
    if not os.path.exists(file_path):
        print(f"Erro: O ficheiro {file_path} não foi encontrado.")
        return

    print("A carregar dataset WUENIC...")
    df = pd.read_excel(file_path, sheet_name="wuenic_master")

    # Normalizar nomes
    df = df.rename(
        columns={
            "Country": "country",
            "ISOCountryCode": "iso_code",
            "Vaccine": "vaccine",
            "Year": "year",
            "WUENIC": "wuenic_coverage",
            "AdministrativeCoverage": "administrative_coverage",
            "ChildrenVaccinated": "children_vaccinated",
            "ChildrenInTarget": "children_target",
            "BirthsUNPD": "births_unpd",
            "SurvivingInfantsUNPD": "surviving_infants",
        }
    )

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
            [tuple(x) for x in country_df.to_numpy()],
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
            [tuple(x) for x in vaccine_df.to_numpy()],
        )

        # -------------------------
        # 3. GET SURROGATE IDS
        # -------------------------
        # Build lookup dicts so we can resolve iso_code -> country_id and
        # vaccine_code -> vaccine_id without issuing a query per fact row
        cur.execute("SELECT iso_code, id FROM country_dim")
        country_map = dict(cur.fetchall())

        cur.execute("SELECT vaccine_code, id FROM vaccine_dim")
        vaccine_map = dict(cur.fetchall())

        # -------------------------
        # 4. FACT TABLE
        # -------------------------
        fact_data = []
        skipped_rows = 0

        for _, row in df.iterrows():
            country_id = country_map.get(row["iso_code"])
            vaccine_id = vaccine_map.get(row["vaccine"])

            if country_id is None or vaccine_id is None:
                skipped_rows += 1
                continue

            fact_data.append(
                (
                    country_id,
                    vaccine_id,
                    row.get("year"),
                    row.get("wuenic_coverage"),
                    row.get("administrative_coverage"),
                    row.get("children_vaccinated"),
                    row.get("children_target"),
                    row.get("births_unpd"),
                    row.get("surviving_infants"),
                    None,   # calculated_coverage: reserved for downstream computation
                    False,  # anomaly_flag: default to False; can be set by a later process
                )
            )

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
            fact_data,
        )

        conn.commit()
        print(f"Sucesso! {len(fact_data)} registos inseridos na immunization_fact.")
        if skipped_rows:
            print(f"Aviso: {skipped_rows} registos ignorados por falta de mapeamento em dimensões.")

    except Exception as e:
        conn.rollback()
        print(f"Erro na ingestão: {e}")

    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    path = "/app/data/wuenic-input.xlsx"
    ingest_wuenic(path)
