from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

SLOT = "main"
ORDER = 30


def render_chart(data: dict[str, pd.DataFrame], summary: dict[str, float | int]) -> None:
    df = data.get("top_conditions_by_drugs", pd.DataFrame())
    top_n = int(summary.get("top_n", 10))
    top_n = max(1, min(top_n, 100))

    if df.empty:
        st.info("No drug data available.")
        return

    df = df.copy()
    df["drug_count"] = pd.to_numeric(df["drug_count"], errors="coerce")
    df["avg_rating"] = pd.to_numeric(df["avg_rating"], errors="coerce")
    df = df.dropna(subset=["drug_count"]).sort_values("drug_count", ascending=True)

    condition = summary.get("global_disease_name")
    if condition:
        st.markdown(f"**Top {top_n} Most Reviewed Drugs for {condition.title()}**")
    else:
        st.markdown(f"**Top {top_n} Medical Conditions by Number of Drugs**")

    fig = px.bar(
        df,
        x="drug_count",
        y="medical_condition",
        orientation="h",
        hover_data={"avg_rating": ":.1f", "drug_count": True},
        labels={
            "drug_count": "Number of Drugs",
            "medical_condition": "Condition",
            "avg_rating": "Avg Rating",
        },
        color="avg_rating",
        color_continuous_scale=["#d62828", "#ffd166", "#3dd5f3"],
    )
    fig.update_layout(
        margin={"l": 0, "r": 0, "t": 10, "b": 0},
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis={"tickfont": {"color": "#e6e6e6"}},
        xaxis={"tickfont": {"color": "#e6e6e6"}, "gridcolor": "rgba(255,255,255,0.1)"},
        coloraxis_colorbar={
            "title": {"text": "Rating", "font": {"color": "#e6e6e6"}},
            "tickfont": {"color": "#e6e6e6"},
        },
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")
    st.caption(
        "Medical conditions with the most available drugs. Color indicates average user rating."
    )
