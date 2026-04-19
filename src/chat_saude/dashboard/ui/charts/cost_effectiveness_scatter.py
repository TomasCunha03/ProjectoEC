from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

SLOT = "main"
ORDER = 50


def render_chart(data: dict[str, pd.DataFrame], summary: dict[str, float | int]) -> None:
    """
    Renders a scatter plot showing cost-effectiveness: treatment cost vs recovery rate.

    Each bubble represents a disease-country combination. Position shows treatment cost
    and recovery rate, bubble size represents number of data points, and color represents
    recovery efficiency (recovery per $1000 spent).

    Helps identify which interventions deliver best outcomes per dollar invested.
    """
    cost_df = data.get("cost_effectiveness", pd.DataFrame())

    if cost_df.empty:
        st.info("No cost-effectiveness data available.")
        return

    st.markdown("**Cost-Effectiveness Map: Treatment Cost vs Recovery Rate**")

    # Prepare data
    cost_df = cost_df.copy()
    cost_df["avg_cost_usd"] = pd.to_numeric(cost_df["avg_cost_usd"], errors="coerce")
    cost_df["avg_recovery_rate"] = pd.to_numeric(cost_df["avg_recovery_rate"], errors="coerce")
    cost_df["data_points"] = pd.to_numeric(cost_df["data_points"], errors="coerce")
    cost_df["recovery_per_1k_usd"] = pd.to_numeric(cost_df["recovery_per_1k_usd"], errors="coerce")

    # Remove rows with missing critical values
    cost_df = cost_df.dropna(subset=["avg_cost_usd", "avg_recovery_rate"])

    if cost_df.empty:
        st.warning("No valid cost-effectiveness data to display.")
        return

    # Create label combining disease and country
    cost_df["label"] = (
        cost_df["disease_name"].astype(str) + " (" + cost_df["country"].astype(str) + ")"
    )

    disease_options = sorted(cost_df["disease_name"].dropna().astype(str).unique().tolist())
    selected_diseases = st.multiselect(
        "Diseases to show",
        options=disease_options,
        default=disease_options,
        key="cost_effectiveness_disease_selector",
    )

    if not selected_diseases:
        st.info("Select at least one disease to render the map.")
        return

    cost_df = cost_df[cost_df["disease_name"].astype(str).isin(selected_diseases)]

    if cost_df.empty:
        st.warning("No cost-effectiveness data for selected diseases.")
        return

    # Create scatter plot
    fig = px.scatter(
        cost_df,
        x="avg_cost_usd",
        y="avg_recovery_rate",
        size="data_points",
        color="recovery_per_1k_usd",
        hover_name="label",
        hover_data={
            "avg_cost_usd": ":.2f",
            "avg_recovery_rate": ":.1f",
            "recovery_per_1k_usd": ":.4f",
            "data_points": True,
            "label": False,
        },
        labels={
            "avg_cost_usd": "Average Treatment Cost (USD)",
            "avg_recovery_rate": "Recovery Rate (%)",
            "recovery_per_1k_usd": "Recovery per $1k",
        },
        color_continuous_scale="RdYlGn",
        size_max=40,
        title=None,
    )

    fig.update_layout(
        height=500,
        xaxis_title="Average Treatment Cost (USD)",
        yaxis_title="Recovery Rate (%)",
        hovermode="closest",
        coloraxis_colorbar=dict(title="Recovery<br>per $1k"),
    )

    st.plotly_chart(fig, use_container_width=True, key="cost_effectiveness")

    # Add summary statistics and insights
    with st.expander("📊 Cost-Effectiveness Summary"):
        col1, col2, col3 = st.columns(3)

        with col1:
            avg_cost = cost_df["avg_cost_usd"].mean()
            st.metric("Average Treatment Cost", f"${avg_cost:,.0f}")

        with col2:
            avg_recovery = cost_df["avg_recovery_rate"].mean()
            st.metric("Average Recovery Rate", f"{avg_recovery:.1f}%")

        with col3:
            avg_efficiency = cost_df["recovery_per_1k_usd"].mean()
            st.metric("Avg Recovery per $1k", f"{avg_efficiency:.4f}")

        st.markdown("**Top Cost-Effective Interventions (Best Recovery per Dollar):**")
        top_efficient = cost_df.nlargest(5, "recovery_per_1k_usd")[
            ["disease_name", "country", "avg_cost_usd", "avg_recovery_rate", "recovery_per_1k_usd"]
        ].copy()
        top_efficient.columns = [
            "Disease",
            "Country",
            "Avg Cost ($)",
            "Recovery Rate (%)",
            "Recovery per $1k",
        ]
        st.dataframe(
            top_efficient,
            use_container_width=True,
            hide_index=True,
        )

        st.markdown("**Most Expensive Interventions:**")
        expensive = cost_df.nlargest(5, "avg_cost_usd")[
            ["disease_name", "country", "avg_cost_usd", "avg_recovery_rate"]
        ].copy()
        expensive.columns = ["Disease", "Country", "Avg Cost ($)", "Recovery Rate (%)"]
        st.dataframe(
            expensive,
            use_container_width=True,
            hide_index=True,
        )
