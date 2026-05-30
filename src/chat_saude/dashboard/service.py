"""
Database access layer for the health dashboard.

``DashboardDataService`` is the single point of contact between the UI layer
and the SQL database.  Each public method maps 1-to-1 to a query builder in
``queries.py``, executes it via a shared SQLAlchemy engine, and returns the
result as a ``pandas.DataFrame``.

The engine is obtained lazily through ``get_engine()`` on first instantiation;
the service object itself is cached at the Streamlit resource level so the
engine is not re-created on every page interaction.
"""

from typing import Any

import pandas as pd
from sqlalchemy.sql.elements import TextClause

from chat_saude.infrastructure.database.postgres import get_engine

from . import queries
from .filters import DashboardFilters


class DashboardDataService:
    """Thin data-access facade: builds queries, runs them, returns DataFrames."""

    def __init__(self):
        self._engine = get_engine()

    def _run(self, statement: TextClause, params: dict[str, Any] | None = None) -> pd.DataFrame:
        """Execute a parameterised SQLAlchemy text statement and return a DataFrame."""
        with self._engine.connect() as conn:
            return pd.read_sql_query(statement, conn, params=params or {})

    def get_global_kpis(self, filters: DashboardFilters) -> pd.DataFrame:
        """Return a single-row DataFrame with global aggregate KPIs."""
        statement, params = queries.global_kpis_query(filters)
        return self._run(statement, params)

    def get_global_yearly_trend(self, filters: DashboardFilters) -> pd.DataFrame:
        """Return year-by-year average mortality and recovery rates."""
        statement, params = queries.global_yearly_trend_query(filters)
        return self._run(statement, params)

    def get_global_country_mortality(self, filters: DashboardFilters) -> pd.DataFrame:
        """Return per-country mortality data used for the globe visualisation."""
        statement, params = queries.global_country_mortality_query(filters)
        return self._run(statement, params)

    def get_global_top_categories(self, filters: DashboardFilters) -> pd.DataFrame:
        """Return the top 10 disease categories by average prevalence rate."""
        statement, params = queries.global_top_categories_query(filters)
        return self._run(statement, params)

    def get_chronic_kpis(self, filters: DashboardFilters) -> pd.DataFrame:
        """Return a single-row DataFrame with chronic disease aggregate KPIs."""
        statement, params = queries.chronic_kpis_query(filters)
        return self._run(statement, params)

    def get_chronic_yearly_trend(self, filters: DashboardFilters) -> pd.DataFrame:
        """Return year-by-year chronic indicator values with confidence interval bounds."""
        statement, params = queries.chronic_yearly_trend_query(filters)
        return self._run(statement, params)

    def get_chronic_top_topics(self, filters: DashboardFilters) -> pd.DataFrame:
        """Return the top 10 chronic disease topics by average indicator value."""
        statement, params = queries.chronic_top_topics_query(filters)
        return self._run(statement, params)

    def get_chronic_top_locations(self, filters: DashboardFilters) -> pd.DataFrame:
        """Return the top 10 US states/locations by average chronic indicator value."""
        statement, params = queries.chronic_top_locations_query(filters)
        return self._run(statement, params)

    def get_bcg_coverage_2023(self, filters: DashboardFilters) -> pd.DataFrame:
        """Return per-country immunization administrative coverage for the selected year."""
        statement, params = queries.bcg_coverage_2023_query(filters)
        return self._run(statement, params)

    def get_bcg_trend(self, filters: DashboardFilters) -> pd.DataFrame:
        """Return year-by-year average/min/max immunization coverage across countries."""
        statement, params = queries.bcg_trend_query(filters)
        return self._run(statement, params)

    def get_global_filter_options(self) -> dict[str, Any]:
        """Return the available year range, countries, and disease categories for filter widgets.

        Reads a single aggregated row so all values come from one DB round-trip.
        Falls back to empty lists when ARRAY_AGG returns NULL (empty table).
        """
        statement = queries.global_filter_options_query()
        df = self._run(statement)
        row = df.iloc[0]
        return {
            "min_year": int(row["min_year"]),
            "max_year": int(row["max_year"]),
            "countries": row["countries"] or [],
            "disease_categories": row["disease_categories"] or [],
        }

    def get_chronic_filter_options(self) -> dict[str, Any]:
        """Return the available year range, locations, and topics for chronic filter widgets."""
        statement = queries.chronic_filter_options_query()
        df = self._run(statement)
        row = df.iloc[0]
        return {
            "min_year": int(row["min_year"]),
            "max_year": int(row["max_year"]),
            "locations": row["locations"] or [],
            "topics": row["topics"] or [],
        }

    def get_risk_factor_disease_correlation(self, filters: DashboardFilters) -> pd.DataFrame:
        """Get risk factor vs disease diagnosis correlation from BRFSS data."""
        statement, params = queries.risk_factor_disease_query(filters)
        return self._run(statement, params)

    def get_cost_effectiveness(self, filters: DashboardFilters) -> pd.DataFrame:
        """Get cost-effectiveness analysis: treatment cost vs recovery rate."""
        statement, params = queries.cost_effectiveness_query(filters)
        return self._run(statement, params)

    def get_top_conditions_by_drugs(self, filters: DashboardFilters) -> pd.DataFrame:
        """Return top conditions by drug count, or top drugs for a specific condition."""
        statement, params = queries.top_conditions_by_drugs_query(filters)
        return self._run(statement, params)

    def get_avg_rating_by_condition(self, filters: DashboardFilters) -> pd.DataFrame:
        """Return top conditions by average drug rating, or top-rated drugs for a condition."""
        statement, params = queries.avg_rating_by_condition_query(filters)
        return self._run(statement, params)

    def get_pregnancy_category(self, filters: DashboardFilters) -> pd.DataFrame:
        """Return drug counts grouped by FDA pregnancy safety category."""
        statement, params = queries.pregnancy_category_query(filters)
        return self._run(statement, params)
