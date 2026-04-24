from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

SLOT = "main"
ORDER = 20


def render_chart(data: dict[str, pd.DataFrame], summary: dict[str, object]) -> None:
    """
    Renders a horizontal bar chart of immunization administrative coverage by country.

    Displays countries sorted by coverage percentage with color gradient:
    - Green: high coverage (>85%)
    - Yellow: medium coverage (50-85%)
    - Red: low coverage (<50%)
    """
    coverage_df = data.get("bcg_coverage_2023", pd.DataFrame())
    top_n = int(summary.get("top_n", 10))
    top_n = max(1, min(top_n, 100))

    selected_year = summary.get("immunization_end_year") or summary.get("immunization_start_year")
    year_label = str(selected_year) if selected_year else "2023"
    raw_vaccine_code = summary.get("vaccine_code")
    vaccine_code = raw_vaccine_code.strip().upper() if isinstance(raw_vaccine_code, str) else ""
    vaccine_scope = f"{vaccine_code} Vaccine" if vaccine_code else "All Vaccines"

    if coverage_df.empty:
        st.info(f"No immunization coverage data available in SQL for {year_label}.")
        return

    st.markdown(
        f"**{vaccine_scope} Administrative Coverage by Country ({year_label}) - Top {top_n}**"
    )

    # Prepare data
    coverage_df = coverage_df.copy()
    input_rows = len(coverage_df)
    coverage_df["administrative_coverage"] = pd.to_numeric(
        coverage_df["administrative_coverage"], errors="coerce"
    )

    # Remove null values
    coverage_df = coverage_df.dropna(subset=["administrative_coverage", "country"])
    coverage_df = coverage_df[
        coverage_df["administrative_coverage"].between(0, 100, inclusive="both")
    ]
    invalid_rows = input_rows - len(coverage_df)

    if coverage_df.empty:
        st.warning(f"No valid immunization coverage data for {year_label}.")
        return

    # Keep only the top N countries by coverage.
    coverage_df = coverage_df.sort_values("administrative_coverage", ascending=False).head(top_n)

    # Sort for horizontal visualization (lowest to highest within top N).
    coverage_df = coverage_df.sort_values("administrative_coverage", ascending=True)

    # Create horizontal bar chart
    fig = px.bar(
        coverage_df,
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
        height=max(400, len(coverage_df) * 15),  # Dynamic height based on number of countries
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
            range=[0, 100],
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
        "total_countries": len(coverage_df),
        "avg_coverage": coverage_df["administrative_coverage"].mean(),
        "min_coverage": coverage_df["administrative_coverage"].min(),
        "max_coverage": coverage_df["administrative_coverage"].max(),
        "high_coverage_count": len(coverage_df[coverage_df["administrative_coverage"] >= 85]),
    }

    st.caption(
        f"📊 Top {coverage_stats['total_countries']} countries | "
        f"Average: {coverage_stats['avg_coverage']:.1f}% | "
        f"Range: {coverage_stats['min_coverage']:.0f}% - {coverage_stats['max_coverage']:.0f}% | "
        f"🟢 High coverage (≥85%): {coverage_stats['high_coverage_count']}"
    )
    if invalid_rows > 0:
        st.caption(
            f"Data quality note: {invalid_rows} records outside 0-100% (or invalid) were excluded."
        )
