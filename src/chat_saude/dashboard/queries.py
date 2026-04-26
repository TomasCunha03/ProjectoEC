from typing import Any

from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

from chat_saude.dashboard.filters import DashboardFilters


def _resolve_top_n(filters: DashboardFilters, default: int = 10) -> int:
    if filters.top_n is None:
        return default
    try:
        parsed = int(filters.top_n)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, 100))


def _build_global_where(filters: DashboardFilters) -> tuple[str, dict[str, Any]]:
    clauses = ["1=1"]
    params: dict[str, Any] = {}

    if filters.global_start_year is not None:
        clauses.append("year >= :global_start_year")
        params["global_start_year"] = filters.global_start_year

    if filters.global_end_year is not None:
        clauses.append("year <= :global_end_year")
        params["global_end_year"] = filters.global_end_year

    if filters.global_country:
        clauses.append("country ILIKE :global_country")
        params["global_country"] = filters.global_country

    if filters.global_disease_name:
        clauses.append("disease_name ILIKE :global_disease_name")
        params["global_disease_name"] = f"%{filters.global_disease_name}%"

    if filters.global_disease_category:
        clauses.append("disease_category ILIKE :global_disease_category")
        params["global_disease_category"] = f"%{filters.global_disease_category}%"

    return " AND ".join(clauses), params


def _build_chronic_where(filters: DashboardFilters) -> tuple[str, dict[str, Any]]:
    clauses = ["1=1"]
    params: dict[str, Any] = {}

    if filters.chronic_start_year is not None:
        clauses.append("year_start >= :chronic_start_year")
        params["chronic_start_year"] = filters.chronic_start_year

    if filters.chronic_end_year is not None:
        clauses.append("year_start <= :chronic_end_year")
        params["chronic_end_year"] = filters.chronic_end_year

    if filters.chronic_location:
        clauses.append("location_desc ILIKE :chronic_location")
        params["chronic_location"] = f"%{filters.chronic_location}%"

    if filters.chronic_topic:
        clauses.append("topic ILIKE :chronic_topic")
        params["chronic_topic"] = f"%{filters.chronic_topic}%"

    return " AND ".join(clauses), params


def global_kpis_query(filters: DashboardFilters) -> tuple[TextClause, dict[str, Any]]:
    where_clause, params = _build_global_where(filters)
    statement = text(
        f"""
        SELECT
            COUNT(DISTINCT country) AS countries_count,
            SUM(population_affected) AS total_population_affected,
            AVG(mortality_rate) AS avg_mortality_rate,
            AVG(recovery_rate) AS avg_recovery_rate
        FROM global_health_stats
        WHERE {where_clause}
        """
    )
    return statement, params


def global_yearly_trend_query(filters: DashboardFilters) -> tuple[TextClause, dict[str, Any]]:
    where_clause, params = _build_global_where(filters)
    statement = text(
        f"""
        SELECT
            year,
            AVG(mortality_rate) AS avg_mortality_rate,
            AVG(recovery_rate) AS avg_recovery_rate
        FROM global_health_stats
        WHERE {where_clause}
          AND year IS NOT NULL
        GROUP BY year
        ORDER BY year
        """
    )
    return statement, params


def global_country_mortality_query(filters: DashboardFilters) -> tuple[TextClause, dict[str, Any]]:
    where_clause, params = _build_global_where(filters)
    statement = text(
        f"""
        SELECT
            country,
            MIN(disease_name) AS disease_name,
            AVG(mortality_rate) AS avg_mortality_rate,
            AVG(recovery_rate) AS avg_recovery_rate,
            SUM(population_affected) AS total_population_affected
        FROM global_health_stats
        WHERE {where_clause}
          AND country IS NOT NULL
          AND mortality_rate IS NOT NULL
        GROUP BY country
        ORDER BY avg_mortality_rate DESC
        """
    )
    return statement, params


def global_top_categories_query(filters: DashboardFilters) -> tuple[TextClause, dict[str, Any]]:
    where_clause, params = _build_global_where(filters)
    statement = text(
        f"""
        SELECT
            disease_category,
            AVG(prevalence_rate) AS avg_prevalence_rate,
            COUNT(*) AS sample_size
        FROM global_health_stats
        WHERE {where_clause}
          AND disease_category IS NOT NULL
          AND prevalence_rate IS NOT NULL
        GROUP BY disease_category
        ORDER BY avg_prevalence_rate DESC
        LIMIT 10
        """
    )
    return statement, params


def chronic_kpis_query(filters: DashboardFilters) -> tuple[TextClause, dict[str, Any]]:
    where_clause, params = _build_chronic_where(filters)
    statement = text(
        f"""
        SELECT
            COUNT(*) AS indicators_count,
            COUNT(DISTINCT location_desc) AS locations_count,
            AVG(data_value) AS avg_data_value
        FROM chronic_disease_indicators
        WHERE {where_clause}
          AND data_value IS NOT NULL
        """
    )
    return statement, params


def chronic_yearly_trend_query(filters: DashboardFilters) -> tuple[TextClause, dict[str, Any]]:
    where_clause, params = _build_chronic_where(filters)
    statement = text(
        f"""
        SELECT
            year_start AS year,
            AVG(data_value) AS avg_data_value,
            AVG(low_confidence_limit) AS avg_low_ci,
            AVG(high_confidence_limit) AS avg_high_ci
        FROM chronic_disease_indicators
        WHERE {where_clause}
          AND year_start IS NOT NULL
          AND data_value IS NOT NULL
        GROUP BY year_start
        ORDER BY year_start
        """
    )
    return statement, params


def chronic_top_topics_query(filters: DashboardFilters) -> tuple[TextClause, dict[str, Any]]:
    where_clause, params = _build_chronic_where(filters)
    statement = text(
        f"""
        SELECT
            topic,
            AVG(data_value) AS avg_data_value,
            COUNT(*) AS sample_size
        FROM chronic_disease_indicators
        WHERE {where_clause}
          AND topic IS NOT NULL
          AND data_value IS NOT NULL
        GROUP BY topic
        ORDER BY avg_data_value DESC
        LIMIT 10
        """
    )
    return statement, params


def chronic_top_locations_query(filters: DashboardFilters) -> tuple[TextClause, dict[str, Any]]:
    where_clause, params = _build_chronic_where(filters)
    statement = text(
        f"""
        SELECT
            location_desc,
            AVG(data_value) AS avg_data_value,
            COUNT(*) AS sample_size
        FROM chronic_disease_indicators
        WHERE {where_clause}
          AND location_desc IS NOT NULL
          AND data_value IS NOT NULL
        GROUP BY location_desc
        ORDER BY avg_data_value DESC
        LIMIT 10
        """
    )
    return statement, params


def global_filter_options_query() -> TextClause:
    return text(
        """
        SELECT
            COALESCE(MIN(year), 0) AS min_year,
            COALESCE(MAX(year), 0) AS max_year,
            ARRAY_REMOVE(ARRAY_AGG(DISTINCT country ORDER BY country), NULL) AS countries,
            ARRAY_REMOVE(
                ARRAY_AGG(DISTINCT disease_category ORDER BY disease_category),
                NULL
            ) AS disease_categories
        FROM global_health_stats
        """
    )


def chronic_filter_options_query() -> TextClause:
    return text(
        """
        SELECT
            COALESCE(MIN(year_start), 0) AS min_year,
            COALESCE(MAX(year_start), 0) AS max_year,
            ARRAY_REMOVE(
                ARRAY_AGG(DISTINCT location_desc ORDER BY location_desc),
                NULL
            ) AS locations,
            ARRAY_REMOVE(ARRAY_AGG(DISTINCT topic ORDER BY topic), NULL) AS topics
        FROM chronic_disease_indicators
        """
    )


def bcg_coverage_2023_query(filters: DashboardFilters) -> tuple[TextClause, dict[str, Any]]:
    """Query for immunization administrative coverage by country for a selected year."""
    target_year = filters.immunization_end_year or filters.immunization_start_year or 2023
    vaccine_code = (
        filters.vaccine_code.strip().upper()
        if isinstance(filters.vaccine_code, str) and filters.vaccine_code.strip()
        else None
    )

    params: dict[str, Any] = {"year": target_year}
    vaccine_clause = ""
    if vaccine_code:
        vaccine_clause = "\n          AND vd.vaccine_code = :vaccine_code"
        params["vaccine_code"] = vaccine_code

    statement = text(
        f"""
        SELECT
            cd.country_name AS country,
            imf.year,
            AVG(imf.administrative_coverage) AS administrative_coverage
        FROM immunization_fact imf
        JOIN country_dim cd ON imf.country_id = cd.id
        JOIN vaccine_dim vd ON imf.vaccine_id = vd.id
        WHERE imf.year = :year
          AND imf.administrative_coverage IS NOT NULL
          AND imf.administrative_coverage BETWEEN 0 AND 100
          {vaccine_clause}
        GROUP BY cd.country_name, imf.year
        ORDER BY administrative_coverage DESC
        """
    )
    return statement, params


def bcg_trend_query(filters: DashboardFilters) -> tuple[TextClause, dict[str, Any]]:
    """Query for immunization coverage trend over years (average, min, max across countries)."""
    params: dict[str, Any] = {}
    vaccine_code = (
        filters.vaccine_code.strip().upper()
        if isinstance(filters.vaccine_code, str) and filters.vaccine_code.strip()
        else None
    )
    year_start = filters.immunization_start_year
    year_end = filters.immunization_end_year

    if year_start is not None and year_end is not None and year_start > year_end:
        year_start, year_end = year_end, year_start

    vaccine_clause = ""
    if vaccine_code:
        vaccine_clause = "\n          AND vd.vaccine_code = :vaccine_code"
        params["vaccine_code"] = vaccine_code

    year_clause = ""
    if year_start is not None:
        year_clause += "\n          AND imf.year >= :immunization_start_year"
        params["immunization_start_year"] = year_start
    if year_end is not None:
        year_clause += "\n          AND imf.year <= :immunization_end_year"
        params["immunization_end_year"] = year_end

    statement = text(
        f"""
        WITH country_year_coverage AS (
            SELECT
                imf.country_id,
                imf.year,
                AVG(imf.administrative_coverage) AS country_avg_coverage
            FROM immunization_fact imf
            JOIN vaccine_dim vd ON imf.vaccine_id = vd.id
            WHERE imf.administrative_coverage IS NOT NULL
              AND imf.administrative_coverage BETWEEN 0 AND 100
              AND imf.year IS NOT NULL
              {vaccine_clause}
              {year_clause}
            GROUP BY imf.country_id, imf.year
        )
        SELECT
            year,
            AVG(country_avg_coverage) AS avg_coverage,
            MIN(country_avg_coverage) AS min_coverage,
            MAX(country_avg_coverage) AS max_coverage,
            COUNT(DISTINCT country_id) AS countries_count
        FROM country_year_coverage
        GROUP BY year
        ORDER BY year ASC
        """
    )
    return statement, params


# FIPS codes for US states (BRFSS state_code column)
_BRFSS_STATE_FIPS: dict[str, int] = {
    "Alabama": 1,
    "Alaska": 2,
    "Arizona": 4,
    "Arkansas": 5,
    "California": 6,
    "Colorado": 8,
    "Connecticut": 9,
    "Delaware": 10,
    "Florida": 12,
    "Georgia": 13,
    "Hawaii": 15,
    "Idaho": 16,
    "Illinois": 17,
    "Indiana": 18,
    "Iowa": 19,
    "Kansas": 20,
    "Kentucky": 21,
    "Louisiana": 22,
    "Maine": 23,
    "Maryland": 24,
    "Massachusetts": 25,
    "Michigan": 26,
    "Minnesota": 27,
    "Mississippi": 28,
    "Missouri": 29,
    "Montana": 30,
    "Nebraska": 31,
    "Nevada": 32,
    "New Hampshire": 33,
    "New Jersey": 34,
    "New Mexico": 35,
    "New York": 36,
    "North Carolina": 37,
    "North Dakota": 38,
    "Ohio": 39,
    "Oklahoma": 40,
    "Oregon": 41,
    "Pennsylvania": 42,
    "Rhode Island": 44,
    "South Carolina": 45,
    "South Dakota": 46,
    "Tennessee": 47,
    "Texas": 48,
    "Utah": 49,
    "Vermont": 50,
    "Virginia": 51,
    "Washington": 53,
    "West Virginia": 54,
    "Wisconsin": 55,
    "Wyoming": 56,
}


def resolve_state_fips(location: str) -> int | None:
    """Map a state name (full or partial) to its FIPS code."""
    title = location.strip().title()
    if title in _BRFSS_STATE_FIPS:
        return _BRFSS_STATE_FIPS[title]
    for name, code in _BRFSS_STATE_FIPS.items():
        if title.lower() in name.lower() or name.lower() in title.lower():
            return code
    return None


def risk_factor_disease_query(
    filters: DashboardFilters,
) -> tuple[TextClause, dict[str, Any]]:
    """
    BRFSS risk factor vs disease correlation.
    Optionally filtered to a single US state via chronic_location.
    """
    params: dict[str, Any] = {}
    cte_filter = ""

    if filters.chronic_location:
        fips = resolve_state_fips(filters.chronic_location)
        if fips is not None:
            cte_filter = "WHERE state_code = :state_code"
            params["state_code"] = fips

    # fmt: off
    statement = text(
        f"""
        WITH brfss AS (
            SELECT * FROM brfss_responses
            {cte_filter}
        )
        SELECT
            CASE WHEN smoke_100 = 1 THEN 'Smoker' ELSE 'Non-Smoker' END AS risk_factor,
            'Smoking' AS risk_category,
            SUM(CASE WHEN diagnosed_diabetes = 1 THEN 1 ELSE 0 END) AS diabetes_cases,
            SUM(CASE WHEN diagnosed_asthma = 1 THEN 1 ELSE 0 END) AS asthma_cases,
            SUM(CASE WHEN diagnosed_heart_attack = 1 THEN 1 ELSE 0 END) AS heart_attack_cases,
            SUM(CASE WHEN diagnosed_heart_dis = 1 THEN 1 ELSE 0 END) AS chd_cases,
            SUM(CASE WHEN diagnosed_stroke = 1 THEN 1 ELSE 0 END) AS stroke_cases,
            SUM(CASE WHEN diagnosed_copd = 1 THEN 1 ELSE 0 END) AS copd_cases,
            SUM(CASE WHEN diagnosed_depressive = 1 THEN 1 ELSE 0 END) AS depressive_disorder_cases,
            SUM(CASE WHEN diagnosed_kidney_dis = 1 THEN 1 ELSE 0 END) AS kidney_disease_cases,
            SUM(CASE WHEN diagnosed_arthritis = 1 THEN 1 ELSE 0 END) AS arthritis_cases,
            SUM(CASE WHEN diagnosed_skin_cancer = 1 THEN 1 ELSE 0 END) AS skin_cancer_cases,
            SUM(CASE WHEN diagnosed_other_cancer = 1 THEN 1 ELSE 0 END) AS other_cancer_cases,
            COUNT(*) AS total_respondents
        FROM brfss WHERE smoke_100 IS NOT NULL GROUP BY smoke_100
        UNION ALL
        SELECT
            CASE WHEN high_blood_pressure = 1 THEN 'High BP' ELSE 'Normal BP' END,
            'Blood Pressure',
            SUM(CASE WHEN diagnosed_diabetes = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_asthma = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_heart_attack = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_heart_dis = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_stroke = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_copd = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_depressive = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_kidney_dis = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_arthritis = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_skin_cancer = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_other_cancer = 1 THEN 1 ELSE 0 END),
            COUNT(*)
        FROM brfss WHERE high_blood_pressure IS NOT NULL GROUP BY high_blood_pressure
        UNION ALL
        SELECT
            CASE WHEN high_cholesterol = 1 THEN 'High Chol' ELSE 'Normal Chol' END,
            'Cholesterol',
            SUM(CASE WHEN diagnosed_diabetes = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_asthma = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_heart_attack = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_heart_dis = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_stroke = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_copd = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_depressive = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_kidney_dis = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_arthritis = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_skin_cancer = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_other_cancer = 1 THEN 1 ELSE 0 END),
            COUNT(*)
        FROM brfss WHERE high_cholesterol IS NOT NULL GROUP BY high_cholesterol
        UNION ALL
        SELECT
            CASE WHEN alcohol_binge = 1 THEN 'Binge Drinker' ELSE 'Non-Binge' END,
            'Alcohol Use',
            SUM(CASE WHEN diagnosed_diabetes = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_asthma = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_heart_attack = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_heart_dis = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_stroke = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_copd = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_depressive = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_kidney_dis = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_arthritis = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_skin_cancer = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_other_cancer = 1 THEN 1 ELSE 0 END),
            COUNT(*)
        FROM brfss WHERE alcohol_binge IS NOT NULL GROUP BY alcohol_binge
        UNION ALL
        SELECT
            CASE WHEN exercise_any = 1 THEN 'Exercises' ELSE 'No Exercise' END,
            'Physical Activity',
            SUM(CASE WHEN diagnosed_diabetes = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_asthma = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_heart_attack = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_heart_dis = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_stroke = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_copd = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_depressive = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_kidney_dis = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_arthritis = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_skin_cancer = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_other_cancer = 1 THEN 1 ELSE 0 END),
            COUNT(*)
        FROM brfss WHERE exercise_any IS NOT NULL GROUP BY exercise_any
        UNION ALL
        SELECT
            CASE
                WHEN bmi < 18.5 THEN 'Underweight'
                WHEN bmi < 25 THEN 'Normal Weight'
                WHEN bmi < 30 THEN 'Overweight'
                ELSE 'Obese'
            END,
            'BMI Category',
            SUM(CASE WHEN diagnosed_diabetes = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_asthma = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_heart_attack = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_heart_dis = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_stroke = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_copd = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_depressive = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_kidney_dis = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_arthritis = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_skin_cancer = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_other_cancer = 1 THEN 1 ELSE 0 END),
            COUNT(*)
        FROM brfss WHERE bmi IS NOT NULL
        GROUP BY CASE
            WHEN bmi < 18.5 THEN 'Underweight'
            WHEN bmi < 25 THEN 'Normal Weight'
            WHEN bmi < 30 THEN 'Overweight'
            ELSE 'Obese' END
        UNION ALL
        SELECT
            CASE
                WHEN general_health = 1 THEN 'Excellent Health'
                WHEN general_health = 2 THEN 'Very Good Health'
                WHEN general_health = 3 THEN 'Good Health'
                WHEN general_health = 4 THEN 'Fair Health'
                WHEN general_health = 5 THEN 'Poor Health'
                ELSE 'Unknown Health'
            END,
            'Self-Rated Health',
            SUM(CASE WHEN diagnosed_diabetes = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_asthma = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_heart_attack = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_heart_dis = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_stroke = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_copd = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_depressive = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_kidney_dis = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_arthritis = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_skin_cancer = 1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN diagnosed_other_cancer = 1 THEN 1 ELSE 0 END),
            COUNT(*)
        FROM brfss WHERE general_health IS NOT NULL GROUP BY general_health
        """
    )
    # fmt: on
    return statement, params


def cost_effectiveness_query(filters: DashboardFilters) -> tuple[TextClause, dict[str, Any]]:
    """
    Query for cost-effectiveness analysis: treatment cost vs recovery rate by disease/country.
    Shows which interventions deliver best outcomes per dollar spent.
    """
    where_clause, params = _build_global_where(filters)
    statement = text(
        f"""
        SELECT
            disease_name,
            country,
            ROUND(AVG(average_treatment_cost_usd)::numeric, 2) AS avg_cost_usd,
            ROUND(AVG(recovery_rate)::numeric, 2) AS avg_recovery_rate,
            COUNT(*) AS data_points,
            ROUND((AVG(recovery_rate) / NULLIF(AVG(average_treatment_cost_usd), 0)
                * 1000)::numeric, 4) AS recovery_per_1k_usd
        FROM global_health_stats
        WHERE {where_clause}
          AND average_treatment_cost_usd IS NOT NULL
          AND average_treatment_cost_usd > 0
          AND recovery_rate IS NOT NULL
          AND disease_name IS NOT NULL
          AND country IS NOT NULL
        GROUP BY disease_name, country
        ORDER BY recovery_per_1k_usd DESC NULLS LAST
        """
    )
    return statement, params


def top_conditions_by_drugs_query(
    filters: DashboardFilters,
) -> tuple[TextClause, dict[str, Any]]:
    """Top N conditions by drug count (overview) or top drugs for a condition (zoom)."""
    top_n = _resolve_top_n(filters)
    if filters.global_disease_name:
        # Zoom in: show individual drugs for the selected condition
        statement = text(
            """
            SELECT
                drug_name        AS medical_condition,
                no_of_reviews    AS drug_count,
                rating           AS avg_rating
            FROM drugs_side_effects
            WHERE medical_condition ILIKE :condition
              AND drug_name IS NOT NULL
              AND no_of_reviews IS NOT NULL
            ORDER BY no_of_reviews DESC NULLS LAST
            LIMIT :top_n
            """
        )
        return statement, {"condition": f"%{filters.global_disease_name}%", "top_n": top_n}

    statement = text(
        """
        SELECT
            medical_condition,
            COUNT(*) AS drug_count,
            AVG(rating) AS avg_rating
        FROM drugs_side_effects
        WHERE medical_condition IS NOT NULL
        GROUP BY medical_condition
        ORDER BY drug_count DESC
        LIMIT :top_n
        """
    )
    return statement, {"top_n": top_n}


def avg_rating_by_condition_query(
    filters: DashboardFilters,
) -> tuple[TextClause, dict[str, Any]]:
    """Top N conditions by avg rating (overview) or top-rated drugs for a condition (zoom)."""
    top_n = _resolve_top_n(filters)
    if filters.global_disease_name:
        # Zoom in: individual drug ratings for the selected condition
        statement = text(
            """
            SELECT
                drug_name     AS medical_condition,
                rating        AS avg_rating,
                no_of_reviews AS drug_count
            FROM drugs_side_effects
            WHERE medical_condition ILIKE :condition
              AND rating IS NOT NULL
              AND drug_name IS NOT NULL
            ORDER BY rating DESC NULLS LAST
            LIMIT :top_n
            """
        )
        return statement, {"condition": f"%{filters.global_disease_name}%", "top_n": top_n}

    statement = text(
        """
        SELECT
            medical_condition,
            AVG(rating) AS avg_rating,
            COUNT(*) AS drug_count
        FROM drugs_side_effects
        WHERE medical_condition IS NOT NULL
          AND rating IS NOT NULL
        GROUP BY medical_condition
        HAVING COUNT(*) >= 5
        ORDER BY avg_rating DESC
        LIMIT :top_n
        """
    )
    return statement, {"top_n": top_n}


def pregnancy_category_query(
    filters: DashboardFilters,
) -> tuple[TextClause, dict[str, Any]]:
    """FDA pregnancy safety categories — optionally filtered to a specific condition."""
    params: dict[str, Any] = {}
    condition_clause = ""
    if filters.global_disease_name:
        condition_clause = "AND medical_condition ILIKE :condition"
        params["condition"] = f"%{filters.global_disease_name}%"

    statement = text(
        f"""
        SELECT
            pregnancy_category,
            COUNT(*) AS drug_count
        FROM drugs_side_effects
        WHERE pregnancy_category IS NOT NULL
          AND pregnancy_category != ''
          AND pregnancy_category != 'N'
          {condition_clause}
        GROUP BY pregnancy_category
        ORDER BY pregnancy_category ASC
        """
    )
    return statement, params
