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
