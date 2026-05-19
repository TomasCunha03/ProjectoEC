from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from typing import cast

import pandas as pd
import streamlit as st

from chat_saude.dashboard.filters import DashboardFilters
from chat_saude.dashboard.ui import charts
from chat_saude.dashboard.ui.data import (
    build_dashboard_summary,
    get_dashboard_data,
)

ChartRenderer = Callable[[dict[str, pd.DataFrame], dict[str, float | int]], None]
ChartEntry = tuple[int, str, ChartRenderer]


def _discover_chart_renderers() -> dict[str, list[ChartEntry]]:
    discovered: dict[str, list[ChartEntry]] = {"main": [], "chronic": [], "future": []}
    package_name = charts.__name__

    for module_info in pkgutil.iter_modules(charts.__path__):
        if module_info.name.startswith("_"):
            continue

        module = importlib.import_module(f"{package_name}.{module_info.name}")
        renderer_obj = getattr(module, "render_chart", None)
        if not callable(renderer_obj):
            continue
        renderer = cast(ChartRenderer, renderer_obj)
        module_name = module_info.name

        slot = str(getattr(module, "SLOT", "main")).lower()
        order = int(getattr(module, "ORDER", 100))

        if slot not in discovered:
            discovered[slot] = []

        discovered[slot].append((order, module_name, renderer))

    result: dict[str, list[ChartEntry]] = {}
    for slot, renderers in discovered.items():
        result[slot] = sorted(renderers, key=lambda item: item[0])
    return result


def render_dashboard_section(filters: DashboardFilters) -> None:
    header_col, refresh_col = st.columns([5, 1])
    with header_col:
        st.subheader("📊 Health Dashboard")
        st.caption("Organized by domain: global view, immunization, risk/cost, and drug insights.")

    disease_label = filters.global_disease_name or "All diseases"

    try:
        data = get_dashboard_data(filters)
    except Exception as exc:
        st.error(f"Could not load SQL dashboard data: {exc}")
        return

    summary = build_dashboard_summary(data, filters)

    metric_1, metric_2, metric_3 = st.columns(3)
    with metric_1:
        st.metric("Avg mortality", f"{float(summary['avg_mortality_rate']):.2f}%")
    with metric_2:
        st.metric("Avg recovery", f"{float(summary['avg_recovery_rate']):.2f}%")
    with metric_3:
        st.metric("Countries in scope", f"{int(summary['countries_count'])}")
    st.caption(f"Current disease scope: {disease_label}")

    renderers_by_slot = _discover_chart_renderers()
    main_renderers = renderers_by_slot.get("main", [])
    chronic_renderers = renderers_by_slot.get("chronic", [])
    if not main_renderers and not chronic_renderers:
        st.info("No dashboard charts available.")
        return

    renderer_map = {module_name: renderer for _, module_name, renderer in main_renderers}
    used_modules: set[str] = set()

    def _take_modules(module_names: list[str]) -> list[ChartRenderer]:
        picked: list[ChartRenderer] = []
        for module_name in module_names:
            renderer = renderer_map.get(module_name)
            if renderer is None:
                continue
            picked.append(renderer)
            used_modules.add(module_name)
        return picked

    def _render_in_columns(renderers: list[ChartRenderer], num_cols: int = 2) -> None:
        if not renderers:
            return
        if len(renderers) == 1:
            renderers[0](data, summary)
            return
        cols = st.columns(num_cols)
        for idx, render in enumerate(renderers):
            with cols[idx % num_cols]:
                render(data, summary)

    st.markdown("### 🌍 Global Overview")
    with st.container(border=True):
        _render_in_columns(_take_modules(["mortality_globe"]), num_cols=1)
        _render_in_columns(_take_modules(["global_trend"]), num_cols=1)

    # ── Chronic Disease section ──────────────────────────────────────────────
    if chronic_renderers:
        st.markdown("### 🦠 Chronic Disease (US)")
        chronic_kpis = st.columns(3)
        with chronic_kpis[0]:
            st.metric("Indicators", f"{int(summary.get('chronic_indicators_count', 0)):,}")
        with chronic_kpis[1]:
            st.metric("States / Locations", f"{int(summary.get('chronic_locations_count', 0))}")
        with chronic_kpis[2]:
            st.metric("Avg Indicator Value", f"{float(summary.get('chronic_avg_value', 0)):.1f}")
        chronic_topic = filters.chronic_topic or "All topics"
        chronic_loc = filters.chronic_location or "All states"
        st.caption(f"Scope: {chronic_topic} · {chronic_loc}")
        with st.container(border=True):
            chronic_chart_renderers = [r for _, _, r in chronic_renderers]
            _render_in_columns(chronic_chart_renderers, num_cols=2)

    st.markdown("### ⚠️ Risk and Cost")
    with st.container(border=True):
        _render_in_columns(
            _take_modules(["risk_factor_disease_heatmap", "brfss_lifestyle_profile"]),
            num_cols=2,
        )
        _render_in_columns(_take_modules(["cost_effectiveness_scatter"]), num_cols=1)

    st.markdown("### 💊 Drug Insights")
    with st.container(border=True):
        _render_in_columns(
            _take_modules(
                [
                    "top_conditions_by_drugs",
                    "top_diseases_mortality",
                    "yearly_recovery_trend",
                ]
            ),
            num_cols=2,
        )

    st.markdown("### 💉 Immunization")
    with st.container(border=True):
        _render_in_columns(_take_modules(["bcg_coverage_2023", "bcg_trend"]), num_cols=2)

    remaining = [renderer for _, module_name, renderer in main_renderers if module_name not in used_modules]
    if remaining:
        st.markdown("### ➕ Additional Charts")
        with st.container(border=True):
            _render_in_columns(remaining, num_cols=2)

    future_renderers = renderers_by_slot.get("future", [])
    if future_renderers:
        st.markdown("### 🚧 Upcoming Blocks")
        with st.container(border=True):
            for _, _, render in future_renderers:
                render(data, summary)
