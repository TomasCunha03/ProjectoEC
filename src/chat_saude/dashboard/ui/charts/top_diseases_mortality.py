from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

SLOT = "main"
ORDER = 20


def render_chart(data: dict[str, pd.DataFrame], summary: dict[str, float | int]) -> None:
    df = data.get("avg_rating_by_condition", pd.DataFrame())
    top_n = int(summary.get("top_n", 10))
    top_n = max(1, min(top_n, 100))

    if df.empty:
        st.info("No rating data available.")
        return

    df = df.copy()
    df["avg_rating"] = pd.to_numeric(df["avg_rating"], errors="coerce")
    df["drug_count"] = pd.to_numeric(df["drug_count"], errors="coerce")
    df = df.dropna(subset=["avg_rating"]).sort_values("avg_rating", ascending=True)

    condition = summary.get("global_disease_name")
    if condition:
        st.markdown(f"**Top {top_n} Rated Drugs for {condition.title()}**")
    else:
        st.markdown(f"**Top {top_n} Best-Rated Conditions by Drug Treatment**")

    fig = px.bar(
        df,
        x="avg_rating",
        y="medical_condition",
        orientation="h",
        hover_data={"drug_count": True, "avg_rating": ":.2f"},
        labels={
            "avg_rating": "Avg Rating (0–10)",
            "medical_condition": "Condition",
            "drug_count": "Drugs",
        },
        color="avg_rating",
        color_continuous_scale=["#d62828", "#ffd166", "#3dd5f3"],
        range_color=[5, 9],
    )
    fig.update_layout(
        margin={"l": 0, "r": 0, "t": 10, "b": 0},
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis={"tickfont": {"color": "#e6e6e6"}},
        xaxis={
            "tickfont": {"color": "#e6e6e6"},
            "gridcolor": "rgba(255,255,255,0.1)",
            "range": [0, 10],
        },
        coloraxis_showscale=False,
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")
    st.caption(
        "Average user rating of drug treatments per condition (min. 5 drugs). "
        "Higher = better-rated treatments."
    )
