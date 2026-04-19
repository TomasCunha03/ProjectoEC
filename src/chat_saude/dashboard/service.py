from typing import Any

import pandas as pd
from sqlalchemy.sql.elements import TextClause

from chat_saude.infrastructure.database.postgres import get_engine

from . import queries
from .filters import DashboardFilters


class DashboardDataService:
    def __init__(self):
        self._engine = get_engine()

    def _run(self, statement: TextClause, params: dict[str, Any] | None = None) -> pd.DataFrame:
        with self._engine.connect() as conn:
            return pd.read_sql_query(statement, conn, params=params or {})

    def get_global_kpis(self, filters: DashboardFilters) -> pd.DataFrame:
        statement, params = queries.global_kpis_query(filters)
        return self._run(statement, params)

    def get_global_yearly_trend(self, filters: DashboardFilters) -> pd.DataFrame:
        statement, params = queries.global_yearly_trend_query(filters)
        return self._run(statement, params)

    def get_global_country_mortality(self, filters: DashboardFilters) -> pd.DataFrame:
        statement, params = queries.global_country_mortality_query(filters)
        return self._run(statement, params)

    def get_global_top_categories(self, filters: DashboardFilters) -> pd.DataFrame:
        statement, params = queries.global_top_categories_query(filters)
        return self._run(statement, params)

    def get_chronic_kpis(self, filters: DashboardFilters) -> pd.DataFrame:
        statement, params = queries.chronic_kpis_query(filters)
        return self._run(statement, params)

    def get_chronic_yearly_trend(self, filters: DashboardFilters) -> pd.DataFrame:
        statement, params = queries.chronic_yearly_trend_query(filters)
        return self._run(statement, params)

    def get_chronic_top_topics(self, filters: DashboardFilters) -> pd.DataFrame:
        statement, params = queries.chronic_top_topics_query(filters)
        return self._run(statement, params)

    def get_chronic_top_locations(self, filters: DashboardFilters) -> pd.DataFrame:
        statement, params = queries.chronic_top_locations_query(filters)
        return self._run(statement, params)

    def get_bcg_coverage_2023(self) -> pd.DataFrame:
        statement, params = queries.bcg_coverage_2023_query()
        return self._run(statement, params)

    def get_bcg_trend(self) -> pd.DataFrame:
        statement, params = queries.bcg_trend_query()
        return self._run(statement, params)

    def get_global_filter_options(self) -> dict[str, Any]:
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
        statement = queries.chronic_filter_options_query()
        df = self._run(statement)
        row = df.iloc[0]
        return {
            "min_year": int(row["min_year"]),
            "max_year": int(row["max_year"]),
            "locations": row["locations"] or [],
            "topics": row["topics"] or [],
        }

    def get_risk_factor_disease_correlation(self) -> pd.DataFrame:
        """Get risk factor vs disease diagnosis correlation from BRFSS data."""
        statement, params = queries.risk_factor_disease_query()
        return self._run(statement, params)

    def get_cost_effectiveness(self, filters: DashboardFilters) -> pd.DataFrame:
        """Get cost-effectiveness analysis: treatment cost vs recovery rate."""
        statement, params = queries.cost_effectiveness_query(filters)
        return self._run(statement, params)
