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
        "global_yearly_trend": service.get_global_yearly_trend(filters),
        "global_map": service.get_global_country_mortality(filters),
        "chronic_kpis": service.get_chronic_kpis(filters),
        "chronic_yearly_trend": service.get_chronic_yearly_trend(filters),
        "chronic_top_topics": service.get_chronic_top_topics(filters),
        "chronic_top_locations": service.get_chronic_top_locations(filters),
        "bcg_coverage_2023": service.get_bcg_coverage_2023(filters),
        "bcg_trend": service.get_bcg_trend(filters),
        "risk_factor_disease": service.get_risk_factor_disease_correlation(filters),
        "cost_effectiveness": service.get_cost_effectiveness(filters),
        "top_conditions_by_drugs": service.get_top_conditions_by_drugs(filters),
        "avg_rating_by_condition": service.get_avg_rating_by_condition(filters),
        "pregnancy_category": service.get_pregnancy_category(filters),
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


def _resolve_top_n(value: object, default: int = 10) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(parsed, 100))


def build_dashboard_summary(
    data: dict[str, pd.DataFrame],
    filters: "DashboardFilters | None" = None,
) -> dict:
    global_kpi_df = data.get("global_kpis", pd.DataFrame())

    summary: dict = {
        "avg_mortality_rate": 0.0,
        "avg_recovery_rate": 0.0,
        "countries_count": 0,
        "global_disease_name": filters.global_disease_name if filters else None,
        "immunization_start_year": filters.immunization_start_year if filters else None,
        "immunization_end_year": filters.immunization_end_year if filters else None,
        "vaccine_code": (filters.vaccine_code.strip().upper() if filters and isinstance(filters.vaccine_code, str) and filters.vaccine_code.strip() else None),
        "top_n": _resolve_top_n(filters.top_n) if filters else 10,
        "chronic_location": filters.chronic_location if filters else None,
    }

    if not global_kpi_df.empty:
        row = global_kpi_df.iloc[0]
        summary["avg_mortality_rate"] = _safe_float(row.get("avg_mortality_rate"))
        summary["avg_recovery_rate"] = _safe_float(row.get("avg_recovery_rate"))
        summary["countries_count"] = _safe_int(row.get("countries_count"))

    chronic_kpi_df = data.get("chronic_kpis", pd.DataFrame())
    summary["chronic_indicators_count"] = 0
    summary["chronic_locations_count"] = 0
    summary["chronic_avg_value"] = 0.0
    if not chronic_kpi_df.empty:
        crow = chronic_kpi_df.iloc[0]
        summary["chronic_indicators_count"] = _safe_int(crow.get("indicators_count"))
        summary["chronic_locations_count"] = _safe_int(crow.get("locations_count"))
        summary["chronic_avg_value"] = _safe_float(crow.get("avg_data_value"))

    return summary
