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


def _discover_chart_renderers() -> dict[str, list[ChartRenderer]]:
    discovered: dict[str, list[tuple[int, ChartRenderer]]] = {"main": [], "future": []}
    package_name = charts.__name__

    for module_info in pkgutil.iter_modules(charts.__path__):
        if module_info.name.startswith("_"):
            continue

        module = importlib.import_module(f"{package_name}.{module_info.name}")
        renderer_obj = getattr(module, "render_chart", None)
        if not callable(renderer_obj):
            continue
        renderer = cast(ChartRenderer, renderer_obj)

        slot = str(getattr(module, "SLOT", "main")).lower()
        order = int(getattr(module, "ORDER", 100))

        if slot not in discovered:
            discovered[slot] = []

        discovered[slot].append((order, renderer))

    result: dict[str, list[ChartRenderer]] = {}
    for slot, renderers in discovered.items():
        ordered = sorted(renderers, key=lambda item: item[0])
        result[slot] = [renderer for _, renderer in ordered]
    return result


def render_dashboard_section(filters: DashboardFilters) -> None:
    st.subheader("📊 Health Dashboard")

    try:
        data = get_dashboard_data(filters)
    except Exception as exc:
        st.error(f"Could not load SQL dashboard data: {exc}")
        return

    summary = build_dashboard_summary(data)

    st.metric(
        "Global average mortality",
        f"{float(summary['avg_mortality_rate']):.2f}%",
        delta=(
            f"Average recovery: {float(summary['avg_recovery_rate']):.2f}% | "
            f"Countries: {int(summary['countries_count'])}"
        ),
    )

    renderers_by_slot = _discover_chart_renderers()
    main_renderers = renderers_by_slot.get("main", [])

    if main_renderers:
        if len(main_renderers) == 1:
            main_renderers[0](data, summary)
        else:
            cols = st.columns(2)
            for idx, render in enumerate(main_renderers):
                with cols[idx % 2]:
                    render(data, summary)

    st.markdown("### Upcoming Blocks")
    with st.container(border=True):
        st.caption("Reserved space for new charts/KPIs triggered by chat filters.")
        future_renderers = renderers_by_slot.get("future", [])
        if future_renderers:
            for render in future_renderers:
                render(data, summary)
        else:
            st.markdown("- Add a new module in src/chat_saude/dashboard/ui/charts/")
            st.markdown("- Define SLOT = 'future' and render_chart(data, summary)")
