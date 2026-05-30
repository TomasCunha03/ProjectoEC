"""
ETL pipeline for the CDC U.S. Chronic Disease Indicators (CDI) dataset.

CDI is a collection of standardised, population-level surveillance indicators
for chronic diseases and their risk factors across U.S. states and territories.
This module selects the relevant columns, coerces numeric fields, and
bulk-inserts the data into the ``chronic_disease_indicators`` PostgreSQL table.
"""

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from psycopg2.extras import execute_values

from chat_saude.infrastructure.database.db_connection import get_db_connection

load_dotenv()


def ingest_cdi(csv_path):
    """
    Load, transform, and ingest a CDI CSV file into the database.

    Parameters
    ----------
    csv_path : str
        Absolute path to the CDI CSV file
        (e.g. ``U.S._Chronic_Disease_Indicators.csv``).
    """
    # 1. Load data
    df = pd.read_csv(csv_path)

    # 2. Select and rename columns to match the SQL schema
    cols_to_keep = {
        "YearStart": "year_start",
        "YearEnd": "year_end",
        "LocationAbbr": "location_abbr",
        "LocationDesc": "location_desc",
        "DataSource": "datasource",
        "Topic": "topic",
        "Question": "question",
        "Response": "response",
        "DataValueUnit": "data_value_unit",
        "DataValueType": "data_value_type",
        "DataValue": "data_value",
        "LowConfidenceLimit": "low_confidence_limit",
        "HighConfidenceLimit": "high_confidence_limit",
        "StratificationCategory1": "stratification_category_1",
        "Stratification1": "stratification_1",
        "Geolocation": "geolocation",
        "LocationID": "location_id",
        "TopicID": "topic_id",
        "QuestionID": "question_id",
        "StratificationID1": "stratification_id_1",
    }

    df = df[cols_to_keep.keys()].rename(columns=cols_to_keep)

    # 3. Cleaning: Convert numeric columns and handle errors (e.g. '~')
    numeric_cols = ["data_value", "low_confidence_limit", "high_confidence_limit"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Replace NaNs with None so PostgreSQL stores NULL
    df = df.replace({np.nan: None})

    # 4. Insert
    conn = get_db_connection()
    cur = conn.cursor()

    columns = list(df.columns)
    query = f"INSERT INTO chronic_disease_indicators ({','.join(columns)}) VALUES %s"
    values = [tuple(x) for x in df.to_numpy()]

    try:
        execute_values(cur, query, values)
        conn.commit()
        print(f"Success: Ingested {len(df)} CDI indicator records.")
    except Exception as e:
        conn.rollback()
        print(f"Error during CDI ingestion: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    path = "/app/data/U.S._Chronic_Disease_Indicators.csv"
    ingest_cdi(path)
