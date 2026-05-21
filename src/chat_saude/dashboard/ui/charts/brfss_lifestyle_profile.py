"""
BRFSS population risk-factor prevalence bar chart.

Shows the percentage of survey respondents who fall into the "at-risk"
category for each modifiable lifestyle risk factor.  SLOT = "main", ORDER = 45.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

SLOT = "main"
ORDER = 45

# Risk factor labels that represent the unhealthy/at-risk sub-group within each category.
# Used to select the correct rows when computing the prevalence rate.
_POSITIVE_RISK_FACTORS = {
    "Smoker",
    "High BP",
    "High Chol",
    "Binge Drinker",
    "No Exercise",
    "Obese",
    "Overweight",
    "Fair Health",
    "Poor Health",
}

_CATEGORY_ORDER = [
    "Smoking",
    "Blood Pressure",
    "Cholesterol",
    "Alcohol Use",
    "Physical Activity",
    "BMI Category",
]

_RISK_LABELS = {
    "Smoking": "Smokers",
    "Blood Pressure": "High Blood Pressure",
    "Cholesterol": "High Cholesterol",
    "Alcohol Use": "Binge Drinking",
    "Physical Activity": "No Exercise",
    "BMI Category": "Overweight / Obese",
}

_COLORS = {
    "Smoking": "#d62828",
    "Blood Pressure": "#f77f00",
    "Cholesterol": "#fcbf49",
    "Alcohol Use": "#9b5de5",
    "Physical Activity": "#3dd5f3",
    "BMI Category": "#e63946",
}


def render_chart(data: dict[str, pd.DataFrame], summary: dict[str, float | int]) -> None:
    """Render a horizontal bar chart of population-level risk factor prevalence.

    For each risk category the chart shows what fraction of BRFSS respondents
    belong to the at-risk sub-group (e.g. smokers among all respondents asked
    about smoking).
    """
    df = data.get("risk_factor_disease", pd.DataFrame())

    if df.empty:
        st.info("No BRFSS lifestyle data available.")
        return

    df = df.copy()
    df["total_respondents"] = pd.to_numeric(df["total_respondents"], errors="coerce")

    rates: list[dict] = []
    for category in _CATEGORY_ORDER:
        cat_df = df[df["risk_category"] == category].copy()
        if cat_df.empty:
            continue

        total = cat_df["total_respondents"].sum()
        if total == 0:
            continue

        positive = cat_df[cat_df["risk_factor"].isin(_POSITIVE_RISK_FACTORS)]["total_respondents"].sum()

        # BMI splits into four groups; treat Overweight + Obese as "at risk".
        if category == "BMI Category":
            positive = cat_df[cat_df["risk_factor"].isin({"Overweight", "Obese"})]["total_respondents"].sum()

        rate = round(positive / total * 100, 1)
        rates.append(
            {
                "category": category,
                "label": _RISK_LABELS.get(category, category),
                "rate": rate,
                "color": _COLORS.get(category, "#aaaaaa"),
            }
        )

    if not rates:
        st.info("No lifestyle rate data to display.")
        return

    rates_df = pd.DataFrame(rates).sort_values("rate", ascending=True)

    location = summary.get("chronic_location")
    suffix = f" — {location.title()}" if location else " — All States"
    st.markdown(f"**Population Risk Factor Prevalence (BRFSS{suffix})**")

    fig = go.Figure(
        go.Bar(
            x=rates_df["rate"],
            y=rates_df["label"],
            orientation="h",
            marker_color=rates_df["color"].tolist(),
            text=[f"{r:.1f}%" for r in rates_df["rate"]],
            textposition="outside",
            textfont=dict(color="#e6e6e6"),
        )
    )
    fig.update_layout(
        height=260,
        margin=dict(l=0, r=40, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            title="% of respondents",
            tickfont=dict(color="#e6e6e6"),
            gridcolor="rgba(255,255,255,0.1)",
            range=[0, max(rates_df["rate"]) * 1.2],
        ),
        yaxis=dict(tickfont=dict(color="#e6e6e6")),
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")
    st.caption("Shows the proportion of BRFSS survey respondents with each modifiable risk factor. Filter by US state via chat or the heatmap selector above.")
