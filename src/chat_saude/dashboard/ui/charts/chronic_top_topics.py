from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

SLOT = "chronic"
ORDER = 20


def render_chart(data: dict[str, pd.DataFrame], summary: dict[str, float | int]) -> None:
    df = data.get("chronic_top_topics", pd.DataFrame())

    if df.empty:
        st.info("No chronic disease topic data available.")
        return

    df = df.copy()
    df["avg_data_value"] = pd.to_numeric(df["avg_data_value"], errors="coerce")
    df = df.dropna(subset=["avg_data_value"]).sort_values("avg_data_value", ascending=True)

    location = summary.get("chronic_location")
    suffix = f" — {location.title()}" if location else ""
    st.markdown(f"**Top Chronic Disease Topics{suffix}**")

    fig = px.bar(
        df,
        x="avg_data_value",
        y="topic",
        orientation="h",
        labels={"avg_data_value": "Avg Indicator Value", "topic": "Topic"},
        color="avg_data_value",
        color_continuous_scale="Blues",
    )
    fig.update_layout(
        height=max(250, len(df) * 28),
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        coloraxis_showscale=False,
        yaxis=dict(tickfont=dict(color="#e6e6e6")),
        xaxis=dict(tickfont=dict(color="#e6e6e6"), gridcolor="rgba(255,255,255,0.1)"),
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")
