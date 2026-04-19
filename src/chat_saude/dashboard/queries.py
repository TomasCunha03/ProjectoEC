from typing import Any

from sqlalchemy import text
from sqlalchemy.sql.elements import TextClause

from chat_saude.dashboard.filters import DashboardFilters


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
        clauses.append("country = :global_country")
        params["global_country"] = filters.global_country

    if filters.global_disease_name:
        clauses.append("disease_name = :global_disease_name")
        params["global_disease_name"] = filters.global_disease_name

    if filters.global_disease_category:
        clauses.append("disease_category = :global_disease_category")
        params["global_disease_category"] = filters.global_disease_category

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
        clauses.append("location_desc = :chronic_location")
        params["chronic_location"] = filters.chronic_location

    if filters.chronic_topic:
        clauses.append("topic = :chronic_topic")
        params["chronic_topic"] = filters.chronic_topic

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


def bcg_coverage_2023_query() -> tuple[TextClause, dict[str, Any]]:
    """Query for BCG administrative coverage by country in 2023."""
    statement = text(
        """
        SELECT
            cd.country_name AS country,
            imf.year,
            imf.administrative_coverage
        FROM immunization_fact imf
        JOIN country_dim cd ON imf.country_id = cd.id
        JOIN vaccine_dim vd ON imf.vaccine_id = vd.id
        WHERE vd.vaccine_code = :vaccine_code
          AND imf.year = :year
          AND imf.administrative_coverage IS NOT NULL
        ORDER BY imf.administrative_coverage DESC
        """
    )
    params = {"vaccine_code": "BCG", "year": 2023}
    return statement, params


def bcg_trend_query() -> tuple[TextClause, dict[str, Any]]:
    """Query for BCG coverage trend over years (average, min, max across countries)."""
    statement = text(
        """
        SELECT
            imf.year,
            AVG(imf.administrative_coverage) AS avg_coverage,
            MIN(imf.administrative_coverage) AS min_coverage,
            MAX(imf.administrative_coverage) AS max_coverage,
            COUNT(DISTINCT imf.country_id) AS countries_count
        FROM immunization_fact imf
        JOIN vaccine_dim vd ON imf.vaccine_id = vd.id
        WHERE vd.vaccine_code = :vaccine_code
          AND imf.administrative_coverage IS NOT NULL
          AND imf.year IS NOT NULL
        GROUP BY imf.year
        ORDER BY imf.year ASC
        """
    )
    params = {"vaccine_code": "BCG"}
    return statement, params


def risk_factor_disease_query() -> tuple[TextClause, dict[str, Any]]:
    """
    Query for risk factor vs disease correlation from BRFSS data.
    Returns counts of disease diagnoses grouped by risk factor presence.
    """
    statement = text(
        """
        SELECT
            CASE WHEN smoke_100 = 1 THEN 'Smoker' ELSE 'Non-Smoker' END AS risk_factor,
            'Smoking' AS risk_category,
            SUM(CASE WHEN diagnosed_diabetes = 1 THEN 1 ELSE 0 END) AS diabetes_cases,
            SUM(CASE WHEN diagnosed_asthma = 1 THEN 1 ELSE 0 END) AS asthma_cases,
            SUM(CASE WHEN diagnosed_heart_attack = 1 THEN 1 ELSE 0 END) AS heart_attack_cases,
            SUM(CASE WHEN diagnosed_heart_dis = 1 THEN 1 ELSE 0 END) AS coronary_heart_disease_cases,
            SUM(CASE WHEN diagnosed_stroke = 1 THEN 1 ELSE 0 END) AS stroke_cases,
            SUM(CASE WHEN diagnosed_copd = 1 THEN 1 ELSE 0 END) AS copd_cases,
            SUM(CASE WHEN diagnosed_depressive = 1 THEN 1 ELSE 0 END) AS depressive_disorder_cases,
            SUM(CASE WHEN diagnosed_kidney_dis = 1 THEN 1 ELSE 0 END) AS kidney_disease_cases,
            SUM(CASE WHEN diagnosed_arthritis = 1 THEN 1 ELSE 0 END) AS arthritis_cases,
            SUM(CASE WHEN diagnosed_skin_cancer = 1 THEN 1 ELSE 0 END) AS skin_cancer_cases,
            SUM(CASE WHEN diagnosed_other_cancer = 1 THEN 1 ELSE 0 END) AS other_cancer_cases,
            COUNT(*) AS total_respondents
        FROM brfss_responses
        WHERE smoke_100 IS NOT NULL
        GROUP BY smoke_100
        
        UNION ALL
        
        SELECT
            CASE WHEN high_blood_pressure = 1 THEN 'High BP' ELSE 'Normal BP' END AS risk_factor,
            'Blood Pressure' AS risk_category,
            SUM(CASE WHEN diagnosed_diabetes = 1 THEN 1 ELSE 0 END) AS diabetes_cases,
            SUM(CASE WHEN diagnosed_asthma = 1 THEN 1 ELSE 0 END) AS asthma_cases,
            SUM(CASE WHEN diagnosed_heart_attack = 1 THEN 1 ELSE 0 END) AS heart_attack_cases,
            SUM(CASE WHEN diagnosed_heart_dis = 1 THEN 1 ELSE 0 END) AS coronary_heart_disease_cases,
            SUM(CASE WHEN diagnosed_stroke = 1 THEN 1 ELSE 0 END) AS stroke_cases,
            SUM(CASE WHEN diagnosed_copd = 1 THEN 1 ELSE 0 END) AS copd_cases,
            SUM(CASE WHEN diagnosed_depressive = 1 THEN 1 ELSE 0 END) AS depressive_disorder_cases,
            SUM(CASE WHEN diagnosed_kidney_dis = 1 THEN 1 ELSE 0 END) AS kidney_disease_cases,
            SUM(CASE WHEN diagnosed_arthritis = 1 THEN 1 ELSE 0 END) AS arthritis_cases,
            SUM(CASE WHEN diagnosed_skin_cancer = 1 THEN 1 ELSE 0 END) AS skin_cancer_cases,
            SUM(CASE WHEN diagnosed_other_cancer = 1 THEN 1 ELSE 0 END) AS other_cancer_cases,
            COUNT(*) AS total_respondents
        FROM brfss_responses
        WHERE high_blood_pressure IS NOT NULL
        GROUP BY high_blood_pressure
        
        UNION ALL
        
        SELECT
            CASE WHEN high_cholesterol = 1 THEN 'High Cholesterol' ELSE 'Normal Cholesterol' END AS risk_factor,
            'Cholesterol' AS risk_category,
            SUM(CASE WHEN diagnosed_diabetes = 1 THEN 1 ELSE 0 END) AS diabetes_cases,
            SUM(CASE WHEN diagnosed_asthma = 1 THEN 1 ELSE 0 END) AS asthma_cases,
            SUM(CASE WHEN diagnosed_heart_attack = 1 THEN 1 ELSE 0 END) AS heart_attack_cases,
            SUM(CASE WHEN diagnosed_heart_dis = 1 THEN 1 ELSE 0 END) AS coronary_heart_disease_cases,
            SUM(CASE WHEN diagnosed_stroke = 1 THEN 1 ELSE 0 END) AS stroke_cases,
            SUM(CASE WHEN diagnosed_copd = 1 THEN 1 ELSE 0 END) AS copd_cases,
            SUM(CASE WHEN diagnosed_depressive = 1 THEN 1 ELSE 0 END) AS depressive_disorder_cases,
            SUM(CASE WHEN diagnosed_kidney_dis = 1 THEN 1 ELSE 0 END) AS kidney_disease_cases,
            SUM(CASE WHEN diagnosed_arthritis = 1 THEN 1 ELSE 0 END) AS arthritis_cases,
            SUM(CASE WHEN diagnosed_skin_cancer = 1 THEN 1 ELSE 0 END) AS skin_cancer_cases,
            SUM(CASE WHEN diagnosed_other_cancer = 1 THEN 1 ELSE 0 END) AS other_cancer_cases,
            COUNT(*) AS total_respondents
        FROM brfss_responses
        WHERE high_cholesterol IS NOT NULL
        GROUP BY high_cholesterol
        
        UNION ALL
        
        SELECT
            CASE WHEN alcohol_binge = 1 THEN 'Binge Drinker' ELSE 'Non-Binge' END AS risk_factor,
            'Alcohol Use' AS risk_category,
            SUM(CASE WHEN diagnosed_diabetes = 1 THEN 1 ELSE 0 END) AS diabetes_cases,
            SUM(CASE WHEN diagnosed_asthma = 1 THEN 1 ELSE 0 END) AS asthma_cases,
            SUM(CASE WHEN diagnosed_heart_attack = 1 THEN 1 ELSE 0 END) AS heart_attack_cases,
            SUM(CASE WHEN diagnosed_heart_dis = 1 THEN 1 ELSE 0 END) AS coronary_heart_disease_cases,
            SUM(CASE WHEN diagnosed_stroke = 1 THEN 1 ELSE 0 END) AS stroke_cases,
            SUM(CASE WHEN diagnosed_copd = 1 THEN 1 ELSE 0 END) AS copd_cases,
            SUM(CASE WHEN diagnosed_depressive = 1 THEN 1 ELSE 0 END) AS depressive_disorder_cases,
            SUM(CASE WHEN diagnosed_kidney_dis = 1 THEN 1 ELSE 0 END) AS kidney_disease_cases,
            SUM(CASE WHEN diagnosed_arthritis = 1 THEN 1 ELSE 0 END) AS arthritis_cases,
            SUM(CASE WHEN diagnosed_skin_cancer = 1 THEN 1 ELSE 0 END) AS skin_cancer_cases,
            SUM(CASE WHEN diagnosed_other_cancer = 1 THEN 1 ELSE 0 END) AS other_cancer_cases,
            COUNT(*) AS total_respondents
        FROM brfss_responses
        WHERE alcohol_binge IS NOT NULL
        GROUP BY alcohol_binge
        
        UNION ALL
        
        SELECT
            CASE WHEN exercise_any = 1 THEN 'Exercises' ELSE 'No Exercise' END AS risk_factor,
            'Physical Activity' AS risk_category,
            SUM(CASE WHEN diagnosed_diabetes = 1 THEN 1 ELSE 0 END) AS diabetes_cases,
            SUM(CASE WHEN diagnosed_asthma = 1 THEN 1 ELSE 0 END) AS asthma_cases,
            SUM(CASE WHEN diagnosed_heart_attack = 1 THEN 1 ELSE 0 END) AS heart_attack_cases,
            SUM(CASE WHEN diagnosed_heart_dis = 1 THEN 1 ELSE 0 END) AS coronary_heart_disease_cases,
            SUM(CASE WHEN diagnosed_stroke = 1 THEN 1 ELSE 0 END) AS stroke_cases,
            SUM(CASE WHEN diagnosed_copd = 1 THEN 1 ELSE 0 END) AS copd_cases,
            SUM(CASE WHEN diagnosed_depressive = 1 THEN 1 ELSE 0 END) AS depressive_disorder_cases,
            SUM(CASE WHEN diagnosed_kidney_dis = 1 THEN 1 ELSE 0 END) AS kidney_disease_cases,
            SUM(CASE WHEN diagnosed_arthritis = 1 THEN 1 ELSE 0 END) AS arthritis_cases,
            SUM(CASE WHEN diagnosed_skin_cancer = 1 THEN 1 ELSE 0 END) AS skin_cancer_cases,
            SUM(CASE WHEN diagnosed_other_cancer = 1 THEN 1 ELSE 0 END) AS other_cancer_cases,
            COUNT(*) AS total_respondents
        FROM brfss_responses
        WHERE exercise_any IS NOT NULL
        GROUP BY exercise_any
        
        UNION ALL
        
        SELECT
            CASE 
                WHEN bmi < 18.5 THEN 'Underweight'
                WHEN bmi >= 18.5 AND bmi < 25 THEN 'Normal Weight'
                WHEN bmi >= 25 AND bmi < 30 THEN 'Overweight'
                ELSE 'Obese'
            END AS risk_factor,
            'BMI Category' AS risk_category,
            SUM(CASE WHEN diagnosed_diabetes = 1 THEN 1 ELSE 0 END) AS diabetes_cases,
            SUM(CASE WHEN diagnosed_asthma = 1 THEN 1 ELSE 0 END) AS asthma_cases,
            SUM(CASE WHEN diagnosed_heart_attack = 1 THEN 1 ELSE 0 END) AS heart_attack_cases,
            SUM(CASE WHEN diagnosed_heart_dis = 1 THEN 1 ELSE 0 END) AS coronary_heart_disease_cases,
            SUM(CASE WHEN diagnosed_stroke = 1 THEN 1 ELSE 0 END) AS stroke_cases,
            SUM(CASE WHEN diagnosed_copd = 1 THEN 1 ELSE 0 END) AS copd_cases,
            SUM(CASE WHEN diagnosed_depressive = 1 THEN 1 ELSE 0 END) AS depressive_disorder_cases,
            SUM(CASE WHEN diagnosed_kidney_dis = 1 THEN 1 ELSE 0 END) AS kidney_disease_cases,
            SUM(CASE WHEN diagnosed_arthritis = 1 THEN 1 ELSE 0 END) AS arthritis_cases,
            SUM(CASE WHEN diagnosed_skin_cancer = 1 THEN 1 ELSE 0 END) AS skin_cancer_cases,
            SUM(CASE WHEN diagnosed_other_cancer = 1 THEN 1 ELSE 0 END) AS other_cancer_cases,
            COUNT(*) AS total_respondents
        FROM brfss_responses
        WHERE bmi IS NOT NULL
        GROUP BY 
            CASE 
                WHEN bmi < 18.5 THEN 'Underweight'
                WHEN bmi >= 18.5 AND bmi < 25 THEN 'Normal Weight'
                WHEN bmi >= 25 AND bmi < 30 THEN 'Overweight'
                ELSE 'Obese'
            END
        
        UNION ALL
        
        SELECT
            CASE
                WHEN general_health = 1 THEN 'Excellent Health'
                WHEN general_health = 2 THEN 'Very Good Health'
                WHEN general_health = 3 THEN 'Good Health'
                WHEN general_health = 4 THEN 'Fair Health'
                WHEN general_health = 5 THEN 'Poor Health'
                ELSE 'Unknown Health'
            END AS risk_factor,
            'Self-Rated Health' AS risk_category,
            SUM(CASE WHEN diagnosed_diabetes = 1 THEN 1 ELSE 0 END) AS diabetes_cases,
            SUM(CASE WHEN diagnosed_asthma = 1 THEN 1 ELSE 0 END) AS asthma_cases,
            SUM(CASE WHEN diagnosed_heart_attack = 1 THEN 1 ELSE 0 END) AS heart_attack_cases,
            SUM(CASE WHEN diagnosed_heart_dis = 1 THEN 1 ELSE 0 END) AS coronary_heart_disease_cases,
            SUM(CASE WHEN diagnosed_stroke = 1 THEN 1 ELSE 0 END) AS stroke_cases,
            SUM(CASE WHEN diagnosed_copd = 1 THEN 1 ELSE 0 END) AS copd_cases,
            SUM(CASE WHEN diagnosed_depressive = 1 THEN 1 ELSE 0 END) AS depressive_disorder_cases,
            SUM(CASE WHEN diagnosed_kidney_dis = 1 THEN 1 ELSE 0 END) AS kidney_disease_cases,
            SUM(CASE WHEN diagnosed_arthritis = 1 THEN 1 ELSE 0 END) AS arthritis_cases,
            SUM(CASE WHEN diagnosed_skin_cancer = 1 THEN 1 ELSE 0 END) AS skin_cancer_cases,
            SUM(CASE WHEN diagnosed_other_cancer = 1 THEN 1 ELSE 0 END) AS other_cancer_cases,
            COUNT(*) AS total_respondents
        FROM brfss_responses
        WHERE general_health IS NOT NULL
        GROUP BY general_health
        """
    )
    return statement, {}


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
            ROUND((AVG(recovery_rate) / NULLIF(AVG(average_treatment_cost_usd), 0) * 1000)::numeric, 4) AS recovery_per_1k_usd
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
