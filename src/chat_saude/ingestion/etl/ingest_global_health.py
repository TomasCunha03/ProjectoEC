import os

import pandas as pd

# Importas a tua utilidade de conexão que já existe
from chat_saude.infrastructure.database.db_connection import get_db_connection
from dotenv import load_dotenv
from psycopg2.extras import execute_values

# 1. Carregar o .env (podes manter o caminho relativo para ser mais flexível)
load_dotenv()


def ingest_global_stats(csv_path):
    if not os.path.exists(csv_path):
        print(f"Erro: O ficheiro {csv_path} não foi encontrado.")
        return

    # 2. Ler o CSV
    df = pd.read_csv(csv_path)

    # 3. Mapear as colunas do CSV para os nomes da tabela SQL
    # Isto garante que os nomes com % ou espaços não quebrem a query
    columns_map = {
        "Country": "country",
        "Year": "year",
        "Disease Name": "disease_name",
        "Disease Category": "disease_category",
        "Prevalence Rate (%)": "prevalence_rate",
        "Incidence Rate (%)": "incidence_rate",
        "Mortality Rate (%)": "mortality_rate",
        "Age Group": "age_group",
        "Gender": "gender",
        "Population Affected": "population_affected",
        "Healthcare Access (%)": "healthcare_access_pct",
        "Doctors per 1000": "doctors_per_1000",
        "Hospital Beds per 1000": "hospital_beds_per_1000",
        "Treatment Type": "treatment_type",
        "Average Treatment Cost (USD)": "average_treatment_cost_usd",
        "Availability of Vaccines/Treatment": "availability_vaccines_treatment",
        "Recovery Rate (%)": "recovery_rate",
        "DALYs": "dalys",
        "Improvement in 5 Years (%)": "improvement_5yr_pct",
        "Per Capita Income (USD)": "per_capita_income_usd",
        "Education Index": "education_index",
        "Urbanization Rate (%)": "urbanization_rate_pct",
    }

    df = df.rename(columns=columns_map)

    # 4. Conectar e Inserir
    conn = get_db_connection()
    cur = conn.cursor()

    # Prepara a query com ON CONFLICT para evitar erros se correrem o script 2 vezes
    cols = ", ".join(df.columns)
    insert_query = f"""
        INSERT INTO global_health_stats ({cols}) 
        VALUES %s 
        ON CONFLICT (country, year, disease_name, age_group, gender) DO NOTHING
    """

    # Converte o DataFrame para uma lista de tuplos para uma inserção rápida
    data_tuples = [tuple(x) for x in df.to_numpy()]

    try:
        execute_values(cur, insert_query, data_tuples)
        conn.commit()
        print(f"Sucesso: {len(df)} registos inseridos na tabela global_health_stats.")
    except Exception as e:
        conn.rollback()
        print(f"Erro durante a ingestão: {e}")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    # Caminho correto do CSV
    csv_path = "/Users/matildefernandes/Desktop/PEC/Global Health Statistics.csv"
    ingest_global_stats(csv_path)
