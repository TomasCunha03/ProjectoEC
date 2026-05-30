"""
Horizontal bar chart: top US states/locations by chronic indicator value.

SLOT = "chronic", ORDER = 30 — rendered inside the Chronic Disease section.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

SLOT = "chronic"
ORDER = 30


def render_chart(data: dict[str, pd.DataFrame], summary: dict[str, float | int]) -> None:
    """Render a horizontal bar chart of the top US locations by average chronic indicator value.

    The chart height scales with the number of rows so bars remain readable
    regardless of how many locations are returned.
    """
    df = data.get("chronic_top_locations", pd.DataFrame())

    if df.empty:
        st.info("No chronic disease location data available.")
        return

    df = df.copy()
    df["avg_data_value"] = pd.to_numeric(df["avg_data_value"], errors="coerce")
    # Sort ascending so the highest-value bar appears at the top in a horizontal chart.
    df = df.dropna(subset=["avg_data_value"]).sort_values("avg_data_value", ascending=True)

    topic = summary.get("chronic_topic")
    suffix = f" — {topic.title()}" if topic else ""
    st.markdown(f"**Top US Locations by Chronic Indicator{suffix}**")

    fig = px.bar(
        df,
        x="avg_data_value",
        y="location_desc",
        orientation="h",
        labels={"avg_data_value": "Avg Indicator Value", "location_desc": "State / Location"},
        color="avg_data_value",
        color_continuous_scale="Oranges",
    )
    fig.update_layout(
        height=max(250, len(df) * 28),  # dynamic height: ~28 px per bar, minimum 250 px
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        coloraxis_showscale=False,
        yaxis=dict(tickfont=dict(color="#e6e6e6")),
        xaxis=dict(tickfont=dict(color="#e6e6e6"), gridcolor="rgba(255,255,255,0.1)"),
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")
