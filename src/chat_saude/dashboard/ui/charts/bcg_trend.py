from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

SLOT = "main"
ORDER = 30


def render_chart(data: dict[str, pd.DataFrame], summary: dict[str, float | int]) -> None:
    """
    Renders a line chart showing BCG administrative coverage trend over years.

    Displays the evolution of average BCG coverage across all countries by year,
    with confidence band showing min/max coverage ranges from SQL data.
    """
    bcg_trend_df = data.get("bcg_trend", pd.DataFrame())

    if bcg_trend_df.empty:
        st.info("No BCG trend data available in SQL.")
        return

    st.markdown("**BCG Administrative Coverage Trend**")

    # Prepare data
    bcg_trend_df = bcg_trend_df.copy()
    bcg_trend_df["year"] = pd.to_numeric(bcg_trend_df["year"], errors="coerce")
    bcg_trend_df["avg_coverage"] = pd.to_numeric(bcg_trend_df["avg_coverage"], errors="coerce")
    bcg_trend_df["min_coverage"] = pd.to_numeric(bcg_trend_df["min_coverage"], errors="coerce")
    bcg_trend_df["max_coverage"] = pd.to_numeric(bcg_trend_df["max_coverage"], errors="coerce")

    # Remove null values
    bcg_trend_df = bcg_trend_df.dropna(subset=["year", "avg_coverage"])

    if bcg_trend_df.empty:
        st.warning("No valid BCG trend data.")
        return

    # Sort by year
    bcg_trend_df = bcg_trend_df.sort_values("year")

    # Create line chart with confidence band
    fig = px.line(
        bcg_trend_df,
        x="year",
        y="avg_coverage",
        markers=True,
        labels={"year": "Year", "avg_coverage": "Average Coverage (%)"},
        title=None,
        color_discrete_sequence=["#3498db"],
    )

    # Add min/max band
    fig.add_scatter(
        x=bcg_trend_df["year"],
        y=bcg_trend_df["max_coverage"],
        fill=None,
        mode="lines",
        line_color="rgba(52, 152, 219, 0)",
        name="Max Coverage",
        showlegend=False,
        hoverinfo="skip",
    )

    fig.add_scatter(
        x=bcg_trend_df["year"],
        y=bcg_trend_df["min_coverage"],
        fill="tonexty",
        mode="lines",
        line_color="rgba(52, 152, 219, 0)",
        name="Range",
        fillcolor="rgba(52, 152, 219, 0.2)",
        showlegend=True,
        hoverinfo="skip",
    )

    # Update layout
    fig.update_layout(
        height=400,
        margin={"l": 60, "r": 50, "t": 30, "b": 50},
        xaxis_title="Year",
        yaxis_title="Administrative Coverage (%)",
        yaxis=dict(
            range=[0, 105],
            gridcolor="rgba(255,255,255,0.1)",
            showgrid=True,
            gridwidth=1,
        ),
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
        hovermode="x unified",
    )

    # Update line styling
    fig.update_traces(
        selector=dict(mode="lines+markers"),
        line=dict(color="#3498db", width=3),
        marker=dict(size=8, color="#3498db", symbol="circle"),
        hovertemplate="<b>Year %{x}</b><br>Average Coverage: %{y:.2f}%<extra></extra>",
    )

    st.plotly_chart(fig, use_container_width=True, theme="streamlit")

    # Statistics
    latest_year = bcg_trend_df[bcg_trend_df["year"] == bcg_trend_df["year"].max()].iloc[0]
    earliest_year = bcg_trend_df[bcg_trend_df["year"] == bcg_trend_df["year"].min()].iloc[0]

    coverage_change = latest_year["avg_coverage"] - earliest_year["avg_coverage"]
    year_range = int(latest_year["year"] - earliest_year["year"])

    change_indicator = "📈" if coverage_change >= 0 else "📉"

    st.caption(
        f"Years analyzed: {int(earliest_year['year'])}-{int(latest_year['year'])}"
        f" ({year_range} years) | "
        f"Average coverage: {bcg_trend_df['avg_coverage'].mean():.1f}% | "
        f"{change_indicator} Change: {coverage_change:+.1f}pp"
    )
