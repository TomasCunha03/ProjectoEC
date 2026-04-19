from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

SLOT = "main"
ORDER = 40


def render_chart(data: dict[str, pd.DataFrame], summary: dict[str, float | int]) -> None:
    """
    Renders a heatmap showing risk factor vs disease diagnosis correlation from BRFSS data.
    
    Shows which modifiable behaviors (smoking, high BP, high cholesterol, binge drinking)
    are most strongly associated with specific diagnosed conditions (diabetes, heart attack,
    stroke, COPD).
    """
    risk_df = data.get("risk_factor_disease", pd.DataFrame())
    
    if risk_df.empty:
        st.info("No BRFSS risk factor data available.")
        return
    
    st.markdown("**Risk Factor vs Disease Correlation (BRFSS Data)**")
    
    # Prepare data
    risk_df = risk_df.copy()
    
    disease_label_map = {
        "diabetes_cases": "Diabetes",
        "asthma_cases": "Asthma",
        "heart_attack_cases": "Heart Attack",
        "coronary_heart_disease_cases": "Coronary Heart Disease",
        "stroke_cases": "Stroke",
        "copd_cases": "COPD",
        "depressive_disorder_cases": "Depressive Disorder",
        "kidney_disease_cases": "Kidney Disease",
        "arthritis_cases": "Arthritis",
        "skin_cancer_cases": "Skin Cancer",
        "other_cancer_cases": "Other Cancer",
    }
    disease_cols = [col for col in disease_label_map if col in risk_df.columns]

    if not disease_cols:
        st.warning("No diagnosis columns available for heatmap.")
        return
    
    # Normalize by total respondents to get rates
    for col in disease_cols:
        risk_df[col] = pd.to_numeric(risk_df[col], errors="coerce")
    
    risk_df["total_respondents"] = pd.to_numeric(
        risk_df["total_respondents"], errors="coerce"
    )
    
    # Calculate prevalence rates (%)
    for col in disease_cols:
        rate_col = col.replace("_cases", "_rate")
        risk_df[rate_col] = (
            (risk_df[col] / risk_df["total_respondents"].replace(0, 1)) * 100
        ).round(2)
    
    default_diseases = [
        "Diabetes",
        "Heart Attack",
        "Stroke",
        "COPD",
    ]
    available_diseases = [disease_label_map[col] for col in disease_cols]
    
    # Selectors for diseases and risk categories
    col1, col2 = st.columns(2)
    
    with col1:
        selected_diseases = st.multiselect(
            "Diseases to show",
            options=available_diseases,
            default=[d for d in default_diseases if d in available_diseases] or available_diseases,
            key="risk_heatmap_disease_selector_v3",
        )

    if not selected_diseases:
        st.info("Select at least one disease to render the heatmap.")
        return
    
    available_categories = sorted(risk_df["risk_category"].dropna().unique().tolist())
    
    with col2:
        selected_categories = st.multiselect(
            "Risk factors to show",
            options=available_categories,
            default=available_categories,
            key="risk_heatmap_category_selector_v2",
        )
    
    if not selected_categories:
        st.info("Select at least one risk factor category to render the heatmap.")
        return
    
    risk_df = risk_df[risk_df["risk_category"].isin(selected_categories)]
    
    # Prepare data for heatmap: group by risk_factor and aggregate
    heatmap_data = []
    for _, row in risk_df.iterrows():
        risk_factor = row["risk_factor"]
        risk_category = row["risk_category"]
        for cases_col in disease_cols:
            disease_name = disease_label_map[cases_col]
            if disease_name not in selected_diseases:
                continue
            rate_col = cases_col.replace("_cases", "_rate")
            heatmap_data.append({
                "Risk Factor": risk_factor,
                "Risk Category": risk_category,
                "Disease": disease_name,
                "Prevalence Rate (%)": row[rate_col],
            })
    
    heatmap_df = pd.DataFrame(heatmap_data)
    
    if heatmap_df.empty:
        st.warning("No valid risk factor data to display.")
        return
    
    # Create pivot for heatmap
    pivot_df = heatmap_df.pivot_table(
        index="Risk Factor",
        columns="Disease",
        values="Prevalence Rate (%)",
        aggfunc="mean"
    )
    
    # Create the heatmap using plotly
    fig = px.imshow(
        pivot_df,
        labels=dict(x="Disease", y="Risk Factor", color="Prevalence Rate (%)"),
        x=pivot_df.columns,
        y=pivot_df.index,
        color_continuous_scale="RdYlGn_r",
        aspect="auto",
        title=None,
    )
    
    fig.update_layout(
        height=400,
        xaxis_title="Disease",
        yaxis_title="Risk Factor",
        coloraxis_colorbar=dict(title="Rate (%)"),
        hovermode="closest",
    )
    
    st.plotly_chart(fig, use_container_width=True, key="risk_heatmap")
    
    # Add summary statistics
    with st.expander("📋 Detailed Statistics"):
        st.dataframe(
            heatmap_df.sort_values("Prevalence Rate (%)", ascending=False),
            use_container_width=True,
            hide_index=True,
        )
        
        # Key insights
        st.markdown("**Key Insights:**")
        top_association = heatmap_df.nlargest(3, "Prevalence Rate (%)")
        for _, row in top_association.iterrows():
            st.write(
                f"- **{row['Risk Factor']}** shows {row['Prevalence Rate (%)']:.1f}% "
                f"prevalence rate for **{row['Disease']}**"
            )
