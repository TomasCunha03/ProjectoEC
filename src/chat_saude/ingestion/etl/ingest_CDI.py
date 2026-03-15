import numpy as np
import pandas as pd
from chat_saude.infrastructure.database.db_connection import get_db_connection
from dotenv import load_dotenv
from psycopg2.extras import execute_values

load_dotenv()


def ingest_cdi(csv_path):
    # 1. Carregar dados
    df = pd.read_csv(csv_path)

    # 2. Selecionar e renomear colunas para corresponder ao SQL
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

    # 3. Limpeza: Converter colunas numéricas e tratar erros (como o '~')
    numeric_cols = ["data_value", "low_confidence_limit", "high_confidence_limit"]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Substituir NaNs por None para o PostgreSQL aceitar como NULL
    df = df.replace({np.nan: None})

    # 4. Inserção
    conn = get_db_connection()
    cur = conn.cursor()

    columns = list(df.columns)
    query = f"INSERT INTO chronic_disease_indicators ({','.join(columns)}) VALUES %s"
    values = [tuple(x) for x in df.to_numpy()]

    try:
        execute_values(cur, query, values)
        conn.commit()
        print(f"Sucesso: {len(df)} indicadores CDI ingeridos.")
    except Exception as e:
        conn.rollback()
        print(f"Erro na ingestão CDI: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    import sys

    path = sys.argv[1] if len(sys.argv) > 1 else "U.S._Chronic_Disease_Indicators.csv"
    ingest_cdi(path)
