from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

SLOT = "main"
ORDER = 20


def render_chart(data: dict[str, pd.DataFrame], summary: dict[str, float | int]) -> None:
    """
    Renders a horizontal bar chart of BCG administrative coverage by country for 2023.

    Displays countries sorted by coverage percentage with color gradient:
    - Green: high coverage (>85%)
    - Yellow: medium coverage (50-85%)
    - Red: low coverage (<50%)
    """
    bcg_2023_df = data.get("bcg_coverage_2023", pd.DataFrame())

    if bcg_2023_df.empty:
        st.info("No BCG coverage data available in SQL for 2023.")
        return

    st.markdown("**BCG Administrative Coverage by Country (2023) - Top 10**")

    # Prepare data
    bcg_2023_df = bcg_2023_df.copy()
    bcg_2023_df["administrative_coverage"] = pd.to_numeric(
        bcg_2023_df["administrative_coverage"], errors="coerce"
    )

    # Remove null values
    bcg_2023_df = bcg_2023_df.dropna(subset=["administrative_coverage", "country"])

    if bcg_2023_df.empty:
        st.warning("No valid BCG coverage data for 2023.")
        return

    # Keep only the top 10 countries by coverage.
    bcg_2023_df = bcg_2023_df.sort_values("administrative_coverage", ascending=False).head(10)

    # Sort for horizontal visualization (lowest to highest within top 10).
    bcg_2023_df = bcg_2023_df.sort_values("administrative_coverage", ascending=True)

    # Color mapping based on coverage percentage
    def get_color(value: float) -> str:
        if value >= 85:
            return "#2ecc71"  # Green - high coverage
        elif value >= 50:
            return "#f39c12"  # Orange - medium coverage
        else:
            return "#e74c3c"  # Red - low coverage

    bcg_2023_df["color"] = bcg_2023_df["administrative_coverage"].apply(get_color)

    # Create horizontal bar chart
    fig = px.bar(
        bcg_2023_df,
        x="administrative_coverage",
        y="country",
        orientation="h",
        color="administrative_coverage",
        color_continuous_scale=[
            [0.0, "#e74c3c"],  # Red for low coverage
            [0.5, "#f39c12"],  # Orange for medium
            [1.0, "#2ecc71"],  # Green for high
        ],
        range_color=(0, 100),
        labels={"administrative_coverage": "Coverage (%)", "country": "Country"},
        title=None,
        hover_data={"country": True, "administrative_coverage": ":.2f"},
    )

    fig.update_layout(
        height=max(400, len(bcg_2023_df) * 15),  # Dynamic height based on number of countries
        margin={"l": 150, "r": 50, "t": 30, "b": 50},
        xaxis_title="Administrative Coverage (%)",
        yaxis_title="",
        showlegend=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            gridcolor="rgba(255,255,255,0.1)",
            showgrid=True,
            gridwidth=1,
        ),
        font=dict(color="#e6e6e6"),
        xaxis_tickfont=dict(color="#e6e6e6"),
        yaxis_tickfont=dict(color="#e6e6e6"),
    )

    fig.update_traces(
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Coverage: %{x:.2f}%<extra></extra>",
    )

    st.plotly_chart(fig, use_container_width=True, theme="streamlit")

    # Statistics
    coverage_stats = {
        "total_countries": len(bcg_2023_df),
        "avg_coverage": bcg_2023_df["administrative_coverage"].mean(),
        "min_coverage": bcg_2023_df["administrative_coverage"].min(),
        "max_coverage": bcg_2023_df["administrative_coverage"].max(),
        "high_coverage_count": len(bcg_2023_df[bcg_2023_df["administrative_coverage"] >= 85]),
    }

    st.caption(
        f"📊 Top {coverage_stats['total_countries']} countries | "
        f"Average: {coverage_stats['avg_coverage']:.1f}% | "
        f"Range: {coverage_stats['min_coverage']:.0f}% - {coverage_stats['max_coverage']:.0f}% | "
        f"🟢 High coverage (≥85%): {coverage_stats['high_coverage_count']}"
    )
