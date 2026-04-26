from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

SLOT = "chronic"
ORDER = 10


def render_chart(data: dict[str, pd.DataFrame], summary: dict[str, float | int]) -> None:
    df = data.get("chronic_yearly_trend", pd.DataFrame())

    if df.empty:
        st.info("No chronic disease trend data available.")
        return

    df = df.copy()
    for col in ["year", "avg_data_value", "avg_low_ci", "avg_high_ci"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["year", "avg_data_value"]).sort_values("year")

    topic = summary.get("chronic_topic")
    location = summary.get("chronic_location")
    parts = []
    if topic:
        parts.append(topic.title())
    if location:
        parts.append(location.title())
    subtitle = " — ".join(parts) if parts else "All Topics & Locations"
    st.markdown(f"**Chronic Disease Indicator Trend — {subtitle}**")

    fig = go.Figure()

    has_ci = df["avg_low_ci"].notna().any() and df["avg_high_ci"].notna().any()
    if has_ci:
        fig.add_trace(
            go.Scatter(
                x=pd.concat([df["year"], df["year"][::-1]]),
                y=pd.concat([df["avg_high_ci"], df["avg_low_ci"][::-1]]),
                fill="toself",
                fillcolor="rgba(61,213,243,0.15)",
                line=dict(color="rgba(0,0,0,0)"),
                showlegend=False,
                name="Confidence Interval",
            )
        )

    fig.add_trace(
        go.Scatter(
            x=df["year"],
            y=df["avg_data_value"],
            name="Avg Indicator Value",
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
        legend=dict(font=dict(color="#e6e6e6")),
        xaxis=dict(
            title="Year",
            tickfont=dict(color="#e6e6e6"),
            gridcolor="rgba(255,255,255,0.1)",
        ),
        yaxis=dict(
            title="Indicator Value",
            tickfont=dict(color="#e6e6e6"),
            gridcolor="rgba(255,255,255,0.1)",
        ),
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")
