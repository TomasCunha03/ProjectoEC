from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

SLOT = "main"
ORDER = 15


def render_chart(data: dict[str, pd.DataFrame], summary: dict[str, float | int]) -> None:
    df = data.get("global_yearly_trend", pd.DataFrame())

    if df.empty:
        st.info("No global trend data available.")
        return

    df = df.copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["avg_mortality_rate"] = pd.to_numeric(df["avg_mortality_rate"], errors="coerce")
    df["avg_recovery_rate"] = pd.to_numeric(df["avg_recovery_rate"], errors="coerce")
    df = df.dropna(subset=["year"]).sort_values("year")

    condition = summary.get("global_disease_name")
    title = f"Global Health Trend — {condition.title()}" if condition else "Global Health Trend"
    st.markdown(f"**{title}**")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["year"],
            y=df["avg_mortality_rate"],
            name="Mortality Rate (%)",
            mode="lines+markers",
            line=dict(color="#d62828", width=2),
            marker=dict(size=5),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["year"],
            y=df["avg_recovery_rate"],
            name="Recovery Rate (%)",
            mode="lines+markers",
            line=dict(color="#3dd5f3", width=2),
            marker=dict(size=5),
        )
    )
    fig.update_layout(
        height=280,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(color="#e6e6e6"),
        ),
        xaxis=dict(
            title="Year",
            tickfont=dict(color="#e6e6e6"),
            gridcolor="rgba(255,255,255,0.1)",
        ),
        yaxis=dict(
            title="Rate (%)",
            tickfont=dict(color="#e6e6e6"),
            gridcolor="rgba(255,255,255,0.1)",
        ),
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")
