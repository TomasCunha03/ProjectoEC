"""
FDA pregnancy safety category bar chart.

Displays the number of drugs in each FDA pregnancy category (A through X).
Category N (not classified) is excluded by the underlying query.

SLOT = "main", ORDER = 40 — rendered in the Drug Insights section.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

SLOT = "main"
ORDER = 40

# Human-readable labels for the five FDA pregnancy risk categories.
_CATEGORY_LABELS = {
    "A": "A – Safe",
    "B": "B – Probably safe",
    "C": "C – Use with caution",
    "D": "D – Evidence of risk",
    "X": "X – Contraindicated",
}

# Colour progression from safe (blue/teal) to contraindicated (red).
_CATEGORY_COLORS = {
    "A": "#3dd5f3",
    "B": "#20a4f3",
    "C": "#ffd166",
    "D": "#f77f00",
    "X": "#d62828",
}


def render_chart(data: dict[str, pd.DataFrame], summary: dict[str, float | int]) -> None:
    """Render a vertical bar chart of drug counts by FDA pregnancy safety category."""
    df = data.get("pregnancy_category", pd.DataFrame())

    if df.empty:
        st.info("No pregnancy category data available.")
        return

    df = df.copy()
    df["drug_count"] = pd.to_numeric(df["drug_count"], errors="coerce")
    # Map raw category codes to descriptive labels; unknown codes fall back to the raw value.
    df["label"] = df["pregnancy_category"].map(_CATEGORY_LABELS).fillna(df["pregnancy_category"])
    df["color"] = df["pregnancy_category"].map(_CATEGORY_COLORS)
    # Sort alphabetically (A→X) so bars appear in the standard FDA risk order.
    df = df.sort_values("pregnancy_category")

    condition = summary.get("global_disease_name")
    if condition:
        st.markdown(f"**Drug Safety in Pregnancy — {condition.title()} Drugs (FDA Categories)**")
    else:
        st.markdown("**Drug Safety in Pregnancy (FDA Categories)**")

    fig = px.bar(
        df,
        x="label",
        y="drug_count",
        labels={"label": "FDA Category", "drug_count": "Number of Drugs"},
        color="label",
        color_discrete_map={row["label"]: row["color"] for _, row in df.iterrows()},
    )
    fig.update_layout(
        margin={"l": 0, "r": 0, "t": 10, "b": 0},
        height=300,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        xaxis={"tickfont": {"color": "#e6e6e6"}, "gridcolor": "rgba(255,255,255,0.1)"},
        yaxis={"tickfont": {"color": "#e6e6e6"}, "gridcolor": "rgba(255,255,255,0.1)"},
    )
    st.plotly_chart(fig, use_container_width=True, theme="streamlit")
    st.caption("FDA pregnancy safety categories: A (safest) → X (contraindicated). Category N (not classified) excluded.")
