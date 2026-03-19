import pandas as pd
from sqlalchemy import text

from chat_saude.infrastructure.database.postgres import get_engine


def _nullable_int(value):
    if pd.isna(value):
        return None
    return int(value)


def _nullable_float(value):
    if pd.isna(value):
        return None
    return float(value)


def _nullable_pct(value):
    """Return percentage compatible with NUMERIC(5,2), else None."""
    if pd.isna(value):
        return None
    val = float(value)
    if abs(val) >= 1000:
        return None
    return round(val, 2)


# WUENIC uses SQLAlchemy engine (engine.begin()), not raw psycopg2
def clean_wuenic_data(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    df = df.drop(
        columns=["Comment", "WUENICPreviousRevision", "GovernmentEstimate"], errors="ignore"
    )

    df = df.dropna(subset=["Country", "Vaccine", "Year"])

    df["Country"] = df["Country"].str.strip().str.upper()
    df["Vaccine"] = df["Vaccine"].str.strip().str.upper()

    df["calculated_coverage"] = (df["ChildrenVaccinated"] / df["ChildrenInTarget"]) * 100

    df["anomaly_flag"] = abs(df["calculated_coverage"] - df["WUENIC"]) > 5

    df = df.drop_duplicates(subset=["Country", "Vaccine", "Year"])

    return df


def ingest_wuenic(filepath: str):
    engine = get_engine()
    df = pd.read_excel(filepath, sheet_name="wuenic_master")
    df = clean_wuenic_data(df)

    with engine.begin() as conn:
        # Insert countries
        countries = df[["ISOCountryCode", "Country"]].drop_duplicates()
        for _, row in countries.iterrows():
            conn.execute(
                text("""
                INSERT INTO country_dim (iso_code, country_name)
                VALUES (:iso, :name)
                ON CONFLICT (iso_code) DO NOTHING
            """),
                {"iso": row["ISOCountryCode"], "name": row["Country"]},
            )

        # Insert vaccines
        vaccines = df[["Vaccine"]].drop_duplicates()
        for _, row in vaccines.iterrows():
            conn.execute(
                text("""
                INSERT INTO vaccine_dim (vaccine_code)
                VALUES (:code)
                ON CONFLICT (vaccine_code) DO NOTHING
            """),
                {"code": row["Vaccine"]},
            )

        # Insert fact records
        for _, row in df.iterrows():
            conn.execute(
                text("""
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
                VALUES (
                    (SELECT id FROM country_dim WHERE iso_code = :iso),
                    (SELECT id FROM vaccine_dim WHERE vaccine_code = :vac),
                    :year,
                    :wuenic,
                    :admin,
                    :vaccinated,
                    :target,
                    :births,
                    :surviving,
                    :calc,
                    :flag
                )
                ON CONFLICT DO NOTHING
            """),
                {
                    "iso": row["ISOCountryCode"],
                    "vac": row["Vaccine"],
                    "year": int(row["Year"]),
                    "wuenic": _nullable_pct(row.get("WUENIC")),
                    "admin": _nullable_pct(row.get("AdministrativeCoverage")),
                    "vaccinated": _nullable_int(row.get("ChildrenVaccinated")),
                    "target": _nullable_int(row.get("ChildrenInTarget")),
                    "births": _nullable_int(row.get("BirthsUNPD")),
                    "surviving": _nullable_int(row.get("SurvivingInfantsUNPD")),
                    "calc": _nullable_pct(row.get("calculated_coverage")),
                    "flag": row.get("anomaly_flag"),
                },
            )


if __name__ == "__main__":
    ingest_wuenic("data/wuenic-input.xlsx")
