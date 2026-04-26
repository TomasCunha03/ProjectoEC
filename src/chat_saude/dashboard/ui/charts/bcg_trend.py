from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

SLOT = "main"
ORDER = 30


def render_chart(data: dict[str, pd.DataFrame], summary: dict[str, object]) -> None:
    """
    Renders a line chart showing immunization administrative coverage trend over years.

    Displays the evolution of average coverage across all countries by year,
    with confidence band showing min/max coverage ranges from SQL data.
    """
    trend_df = data.get("bcg_trend", pd.DataFrame())
    start_year_raw = summary.get("immunization_start_year")
    end_year_raw = summary.get("immunization_end_year")
    raw_vaccine_code = summary.get("vaccine_code")
    vaccine_code = raw_vaccine_code.strip().upper() if isinstance(raw_vaccine_code, str) else ""
    vaccine_scope = f"{vaccine_code} Vaccine" if vaccine_code else "All Vaccines"

    start_year = int(start_year_raw) if isinstance(start_year_raw, int) else None
    end_year = int(end_year_raw) if isinstance(end_year_raw, int) else None
    if start_year is not None and end_year is not None and start_year > end_year:
        start_year, end_year = end_year, start_year

    if trend_df.empty:
        st.info("No immunization trend data available in SQL.")
        return

    if start_year is not None and end_year is not None:
        st.markdown(f"**{vaccine_scope} Administrative Coverage Trend ({start_year}-{end_year})**")
    elif start_year is not None:
        st.markdown(f"**{vaccine_scope} Administrative Coverage Trend (from {start_year})**")
    elif end_year is not None:
        st.markdown(f"**{vaccine_scope} Administrative Coverage Trend (up to {end_year})**")
    else:
        st.markdown(f"**{vaccine_scope} Administrative Coverage Trend**")

    # Prepare data
    trend_df = trend_df.copy()
    trend_df["year"] = pd.to_numeric(trend_df["year"], errors="coerce")
    trend_df["avg_coverage"] = pd.to_numeric(trend_df["avg_coverage"], errors="coerce")
    trend_df["min_coverage"] = pd.to_numeric(trend_df["min_coverage"], errors="coerce")
    trend_df["max_coverage"] = pd.to_numeric(trend_df["max_coverage"], errors="coerce")

    # Remove null values
    trend_df = trend_df.dropna(subset=["year", "avg_coverage"])

    if trend_df.empty:
        st.warning("No valid immunization trend data.")
        return

    # Sort by year
    trend_df = trend_df.sort_values("year")

    if start_year is not None:
        trend_df = trend_df[trend_df["year"] >= start_year]
    if end_year is not None:
        trend_df = trend_df[trend_df["year"] <= end_year]

    if trend_df.empty:
        st.warning("No immunization trend records for the selected year window.")
        return

    # Create line chart with confidence band
    fig = px.line(
        trend_df,
        x="year",
        y="avg_coverage",
        markers=True,
        labels={"year": "Year", "avg_coverage": "Average Coverage (%)"},
        title=None,
        color_discrete_sequence=["#3498db"],
    )

    # Add min/max band
    fig.add_scatter(
        x=trend_df["year"],
        y=trend_df["max_coverage"],
        fill=None,
        mode="lines",
        line_color="rgba(52, 152, 219, 0)",
        name="Max Coverage",
        showlegend=False,
        hoverinfo="skip",
    )

    fig.add_scatter(
        x=trend_df["year"],
        y=trend_df["min_coverage"],
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
    latest_year = trend_df[trend_df["year"] == trend_df["year"].max()].iloc[0]
    earliest_year = trend_df[trend_df["year"] == trend_df["year"].min()].iloc[0]

    coverage_change = latest_year["avg_coverage"] - earliest_year["avg_coverage"]
    year_range = int(latest_year["year"] - earliest_year["year"])

    change_indicator = "📈" if coverage_change >= 0 else "📉"

    st.caption(
        f"Years analyzed: {int(earliest_year['year'])}-{int(latest_year['year'])}"
        f" ({year_range} years) | "
        f"Average coverage: {trend_df['avg_coverage'].mean():.1f}% | "
        f"{change_indicator} Change: {coverage_change:+.1f}pp"
    )
