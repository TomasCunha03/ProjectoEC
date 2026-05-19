from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

SLOT = "main"
ORDER = 10


def render_chart(data: dict[str, pd.DataFrame], summary: dict[str, float | int]) -> None:
    global_map_df = data.get("global_map", pd.DataFrame())

    if global_map_df.empty:
        st.info("No global data available for the orthographic map.")
        return

    selected_disease = summary.get("global_disease_name")
    disease_label = "All diseases"
    if isinstance(selected_disease, str) and selected_disease.strip():
        disease_label = selected_disease.strip()

    st.markdown(f"**Orthographic Globe: Average mortality by country ({disease_label})**")

    global_map_df = global_map_df.copy()
    global_map_df["avg_mortality_rate"] = pd.to_numeric(global_map_df["avg_mortality_rate"], errors="coerce")

    z_min = float(global_map_df["avg_mortality_rate"].min())
    z_max = float(global_map_df["avg_mortality_rate"].max())

    mortality_scale = [
        [0.0, "#3dd5f3"],
        [0.35, "#20a4f3"],
        [0.6, "#ffd166"],
        [0.8, "#f77f00"],
        [1.0, "#d62828"],
    ]

    fig_globe = px.choropleth(
        global_map_df,
        locations="country",
        locationmode="country names",
        color="avg_mortality_rate",
        hover_name="country",
        hover_data={
            "avg_mortality_rate": ":.2f",
            "avg_recovery_rate": ":.2f",
            "total_population_affected": ":,.0f",
        },
        color_continuous_scale=mortality_scale,
        range_color=(z_min, z_max),
        labels={"avg_mortality_rate": "Mortality (%)"},
        title=None,
    )
    fig_globe.update_traces(
        marker_line_color="rgba(255,255,255,0.35)",
        marker_line_width=0.5,
    )
    fig_globe.update_geos(
        projection_type="orthographic",
        projection_rotation={"lon": -20, "lat": 15},
        bgcolor="rgba(0,0,0,0)",
        showland=True,
        landcolor="rgba(48,63,89,0.95)",
        showcountries=True,
        countrycolor="rgba(255,255,255,0.35)",
        showcoastlines=True,
        coastlinecolor="rgba(210,230,255,0.7)",
        showocean=True,
        oceancolor="rgba(6,20,44,1)",
        showlakes=True,
        lakecolor="rgba(6,20,44,1)",
    )
    fig_globe.update_layout(
        margin={"l": 0, "r": 0, "t": 10, "b": 0},
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        coloraxis_colorbar={
            "title": {"text": "Mortality %", "font": {"color": "#e6e6e6"}},
            "tickfont": {"color": "#e6e6e6"},
        },
    )
    st.plotly_chart(fig_globe, use_container_width=True, theme="streamlit")
    st.caption(f"Disease in scope: {disease_label}. Darker color means higher average mortality. Hover to inspect recovery and affected population.")
