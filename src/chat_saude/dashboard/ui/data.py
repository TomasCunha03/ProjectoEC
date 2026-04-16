from __future__ import annotations

import pandas as pd
import streamlit as st

from chat_saude.dashboard.filters import DashboardFilters
from chat_saude.dashboard.service import DashboardDataService


@st.cache_resource
def get_dashboard_service() -> DashboardDataService:
    return DashboardDataService()


@st.cache_data(ttl=300)
def get_dashboard_data(filters: DashboardFilters) -> dict[str, pd.DataFrame]:
    service = get_dashboard_service()
    return {
        "global_kpis": service.get_global_kpis(filters),
        "global_map": service.get_global_country_mortality(filters),
        "bcg_coverage_2023": service.get_bcg_coverage_2023(),
        "bcg_trend": service.get_bcg_trend(),
    }


def clear_dashboard_cache() -> None:
    st.cache_data.clear()


def _safe_float(value: object, default: float = 0.0) -> float:
    if value is None or pd.isna(value):
        return default
    return float(value)


def _safe_int(value: object, default: int = 0) -> int:
    if value is None or pd.isna(value):
        return default
    return int(value)


def build_dashboard_summary(data: dict[str, pd.DataFrame]) -> dict[str, float | int]:
    global_kpi_df = data.get("global_kpis", pd.DataFrame())

    summary = {
        "avg_mortality_rate": 0.0,
        "avg_recovery_rate": 0.0,
        "countries_count": 0,
    }

    if not global_kpi_df.empty:
        row = global_kpi_df.iloc[0]
        summary["avg_mortality_rate"] = _safe_float(row.get("avg_mortality_rate"))
        summary["avg_recovery_rate"] = _safe_float(row.get("avg_recovery_rate"))
        summary["countries_count"] = _safe_int(row.get("countries_count"))

    return summary
