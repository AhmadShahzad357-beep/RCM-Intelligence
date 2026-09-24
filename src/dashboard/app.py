from __future__ import annotations

import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from src.config import PROCESSED_DIR, TABLE_DIR


st.set_page_config(page_title="RCM Intelligence Platform", layout="wide", page_icon="\U0001F4CA")

STATE_NAME = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California",
    "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware", "DC": "District of Columbia",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey",
    "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota",
    "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico", "AK": "Alaska",
}

PALETTE = {
    "blue": "#2E5EAA", "green": "#2E8B57", "orange": "#D98E04",
    "red": "#C0392B", "purple": "#6A4C93", "gray": "#8C8C8C", "teal": "#1B7F79",
}
RISK_COLORS = {"low": PALETTE["green"], "medium": PALETTE["orange"], "high": PALETTE["red"]}


@st.cache_data
def load_data() -> dict:
    data = {}

    def _try(key, loader):
        try:
            data[key] = loader()
        except FileNotFoundError:
            data[key] = None

    _try("national", lambda: pd.read_parquet(PROCESSED_DIR / "ma_scp_monthly_national.parquet"))
    _try("national_bounds", lambda: pd.read_csv(TABLE_DIR / "ma_scp_national_bounds.csv"))
    _try("backtest_summary", lambda: pd.read_csv(TABLE_DIR / "backtest_summary.csv"))
    _try("forecast_metrics", lambda: pd.read_csv(TABLE_DIR / "forecast_metrics.csv"))

    _try("state_opp", lambda: pd.read_csv(TABLE_DIR / "dashboard_state_opportunities.csv"))
    _try("county_opp", lambda: pd.read_csv(TABLE_DIR / "dashboard_county_opportunities.csv"))
    _try("opp_method", lambda: pd.read_csv(TABLE_DIR / "opportunity_score_methodology.csv"))
    _try("opp_sensitivity_state", lambda: pd.read_csv(TABLE_DIR / "opportunity_score_sensitivity_state.csv"))
    _try("opp_sensitivity_county", lambda: pd.read_csv(TABLE_DIR / "opportunity_score_sensitivity_county.csv"))

    _try("pa_plans", lambda: pd.read_csv(TABLE_DIR / "prior_auth_exposure.csv") if (TABLE_DIR / "prior_auth_exposure.csv").exists() else pd.read_csv(PROCESSED_DIR / "pa_predictions.csv"))
    _try("pa_metrics", lambda: pd.read_csv(TABLE_DIR / "pa_model_metrics.csv"))
    _try("pa_members_national", lambda: pd.read_csv(TABLE_DIR / "pa_exposure_by_members_national.csv"))
    _try("pa_members_by_type", lambda: pd.read_csv(TABLE_DIR / "pa_exposure_by_members.csv"))

    _try("payer_ranked", lambda: pd.read_csv(TABLE_DIR / "payer_scorecard_ranked.csv"))
    _try("payer_full", lambda: pd.read_csv(TABLE_DIR / "payer_scorecard_full.csv"))

    _try("hier_state", lambda: pd.read_csv(TABLE_DIR / "hierarchical_state_forecast.csv"))
    _try("hier_county", lambda: pd.read_csv(TABLE_DIR / "hierarchical_county_forecast.csv"))
    _try("hier_summary", lambda: pd.read_csv(TABLE_DIR / "hierarchical_reconciliation_summary.csv"))

    _try("proxy_revenue", lambda: pd.read_csv(TABLE_DIR / "proxy_revenue_scenarios.csv"))
    _try("validation", lambda: pd.read_csv(TABLE_DIR / "model_validation_summary.csv"))

    return data


def whole(v) -> str:
    return f"{v:,.0f}"


def pct(v) -> str:
    return f"{v:.2%}"


def money(v) -> str:
    if abs(v) >= 1_000_000_000:
        return f"${v / 1_000_000_000:,.1f}B"
    if abs(v) >= 1_000_000:
        return f"${v / 1_000_000:,.1f}M"
    return f"${v:,.0f}"


def csv_bytes(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False).encode("utf-8")


def clean_layout(fig, height: int = 420) -> go.Figure:
    fig.update_layout(
        height=height,
        template="plotly_white",
        font=dict(family="Segoe UI, Arial", size=12, color="#1F2937"),
        title_font=dict(size=15, family="Segoe UI, Arial"),
        margin=dict(l=10, r=10, t=55, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#EEF1F5", zeroline=False)
    return fig


def section_header(title: str, subtitle: str) -> None:
    st.subheader(title)
    st.caption(subtitle)


def missing_notice(name: str) -> None:
    st.warning(f"'{name}' hasn't been generated yet. Run the corresponding pipeline step, then reload.")


st.markdown(
    """
    <style>
    .block-container {padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1500px;}
    h1 {font-size: 2.1rem; font-weight: 800; margin-bottom: 0.1rem; color: #111827;}
    h2, h3 {letter-spacing: 0; color: #1F2937;}
    p, .stCaption {color: #4B5563;}
    div[data-testid="stMetric"] {
        background: #FFFFFF; border: 1px solid #E5E7EB; padding: 14px 16px;
        border-radius: 10px; box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
    div[data-testid="stMetricLabel"] {font-size: 0.8rem; color: #6B7280;}
    div[data-testid="stMetricValue"] {font-size: 1.5rem; color: #111827;}
    .hook-box {
        border-left: 4px solid #2E5EAA; padding: 12px 16px; background: #F3F7FD;
        border-radius: 6px; margin-bottom: 0.75rem; color: #1F2937;
    }
    .caveat-box {
        border-left: 4px solid #D98E04; padding: 10px 14px; background: #FEF8EC;
        border-radius: 6px; color: #4B5563; font-size: 0.9rem;
    }
    [data-testid="stSidebar"] {background: #F9FAFB; border-right: 1px solid #E5E7EB;}
    </style>
    """,
    unsafe_allow_html=True,
)

data = load_data()

national = data["national"]
if national is None:
    st.error("Core enrollment data not found. Run `python -m src.data.load_ma_scp` first, then reload this page.")
    st.stop()

national = national.copy().sort_values("report_month")
national["report_month"] = national["report_month"].astype(str)
latest_row = national.iloc[-1]
first_row = national.iloc[0]
latest_label = latest_row["report_month"]
latest_enrollment = latest_row["observed_enrollment"]
national_growth = latest_enrollment - first_row["observed_enrollment"]
national_growth_pct = latest_enrollment / first_row["observed_enrollment"] - 1

bounds = data["national_bounds"]
if bounds is not None:
    bounds = bounds.copy().sort_values("report_month")
    bounds["report_month"] = bounds["report_month"].astype(str)
    latest_bounds = bounds.iloc[-1]

backtest_summary = data["backtest_summary"]
best_model_row = backtest_summary.sort_values("mean_mape").iloc[0] if backtest_summary is not None else None

hier_summary = data["hier_summary"].iloc[0] if data["hier_summary"] is not None else None

with st.sidebar:
    st.title("RCM Intelligence")
    st.caption("Public CMS Medicare Advantage enrollment, penetration, payer, and prior-authorization intelligence.")
    st.metric("CMS data window", f"{national['report_month'].min()} to {latest_label}")
    st.divider()
    st.markdown("**Filters**")
    top_n = st.slider("Rows shown in tables/lists", min_value=10, max_value=50, value=20, step=5)
    if data["pa_plans"] is not None:
        pa_bucket_filter = st.multiselect(
            "PA risk buckets", options=["high", "medium", "low"], default=["high", "medium", "low"]
        )
    else:
        pa_bucket_filter = ["high", "medium", "low"]
    st.divider()
    st.markdown("**Data integrity notes**")
    st.caption(
        "Suppressed CMS cells are reported as a [low, high] range, not dropped. "
        "Forecast reliability is validated with a rolling-origin backtest against a naive baseline, "
        "not a single holdout. PA scores are CMS benefit-field exposure signals, not denial predictions. "
        "Revenue figures are a labeled proxy using a public national PMPM assumption."
    )

st.title("RCM Opportunity Forecasting & Prior Authorization Intelligence")
st.caption("Built entirely from public CMS Medicare Advantage data \u2014 enrollment, penetration, plan benefits, and CPSC contract/plan enrollment.")

tab_overview, tab_forecast, tab_hier, tab_growth, tab_payer, tab_pa, tab_revenue, tab_validation = st.tabs(
    [
        "Executive Overview",
        "Enrollment Forecast",
        "Hierarchical Forecast",
        "Growth Opportunity",
        "Payer Scorecard",
        "PA Exposure",
        "Proxy Revenue",
        "Validation",
    ]
)

with tab_overview:
    section_header("Executive Summary", "What a decision-maker should see first.")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Latest observed MA enrollment", whole(latest_enrollment), f"as of {latest_label}")
    c2.metric("Growth since first observed month", pct(national_growth_pct), f"+{whole(national_growth)}")
    if best_model_row is not None:
        c3.metric("Best forecasting model", best_model_row["model"], f"MASE {best_model_row['mean_mase']:.2f}")
    if data["pa_members_national"] is not None:
        high_share = data["pa_members_national"].set_index("risk_bucket").loc["high", "member_share"]
        c4.metric("Members in high-PA-exposure plans", pct(high_share), "member-weighted")

    if bounds is not None:
        st.markdown(
            f"""<div class="hook-box"><b>Data quality note:</b> the latest month
            ({latest_label}) has <b>{latest_bounds['suppressed_row_share']:.1%}</b> of rows
            suppressed by CMS. Reported enrollment is a range: <b>{whole(latest_bounds['enrolled_low'])}</b>
            to <b>{whole(latest_bounds['enrolled_high'])}</b>, not a single point estimate.</div>""",
            unsafe_allow_html=True,
        )

    left, right = st.columns([1.3, 1])
    with left:
        fig = go.Figure()
        if bounds is not None:
            fig.add_trace(go.Scatter(
                x=pd.concat([bounds["report_month"], bounds["report_month"][::-1]]),
                y=pd.concat([bounds["enrolled_high"], bounds["enrolled_low"][::-1]]),
                fill="toself", fillcolor="rgba(46,94,170,0.12)", line=dict(width=0),
                name="Suppression-adjusted range", hoverinfo="skip",
            ))
        fig.add_trace(go.Scatter(
            x=national["report_month"], y=national["observed_enrollment"],
            mode="lines+markers", name="Actual (observed)", line=dict(color=PALETTE["blue"], width=2.5),
        ))
        fig = clean_layout(fig, height=400)
        fig.update_layout(title="National MA Enrollment Trend")
        st.plotly_chart(fig, width="stretch")
    with right:
        st.markdown("**Top opportunity markets**")
        if data["state_opp"] is not None:
            top_states = data["state_opp"].nlargest(7, "opportunity_score").copy()
            top_states["state_name"] = top_states["state"].map(STATE_NAME).fillna(top_states["state"])
            st.dataframe(
                top_states[["state", "state_name", "opportunity_score", "growth_pct", "last_enrollment"]].rename(
                    columns={"state": "State", "state_name": "Market", "opportunity_score": "Score",
                             "growth_pct": "Growth %", "last_enrollment": "Enrollment"}
                ),
                width="stretch", hide_index=True,
            )
        else:
            missing_notice("dashboard_state_opportunities.csv")

    st.markdown("**Coverage of the analysis**")
    d1, d2, d3, d4 = st.columns(4)
    d1.success("Enrollment forecast, rolling-origin validated")
    d2.success("State + top-county hierarchical forecast")
    d3.success("Payer scorecard, member-weighted")
    d4.success("Proxy revenue, scenario-based")

with tab_forecast:
    section_header("Enrollment Forecast", "Backtest-validated model comparison and national outlook.")

    if backtest_summary is not None:
        c1, c2, c3 = st.columns(3)
        best = backtest_summary.sort_values("mean_mape").iloc[0]
        naive = backtest_summary[backtest_summary["model"] == "naive_last_value"].iloc[0]
        c1.metric("Best model", best["model"], f"{int(best['n_splits'])} rolling splits")
        c2.metric("Model MASE vs. naive MASE", f"{best['mean_mase']:.2f}", f"naive: {naive['mean_mase']:.2f}")
        c3.metric("Mean MAPE", pct(best["mean_mape"]))

        fig = go.Figure()
        bt = backtest_summary.sort_values("mean_mase")
        colors = [PALETTE["green"] if m == best["model"] else PALETTE["gray"] for m in bt["model"]]
        fig.add_trace(go.Bar(x=bt["model"], y=bt["mean_mase"], marker_color=colors, text=bt["mean_mase"].round(2), textposition="outside"))
        fig = clean_layout(fig, height=380)
        fig.update_layout(title="Rolling-Origin Backtest: Mean MASE by Model (lower is better)", showlegend=False)
        st.plotly_chart(fig, width="stretch")

        st.markdown(
            """<div class="caveat-box">MASE compares each model to a naive
            "next month = this month" forecast on the same multi-step horizon, averaged across
            15 rolling-origin splits \u2014 not a single lucky holdout. A model beating the naive
            baseline's own MASE is the correct bar for a 3-month-ahead forecast.</div>""",
            unsafe_allow_html=True,
        )
    else:
        missing_notice("backtest_summary.csv")

    if data["forecast_metrics"] is not None:
        with st.expander("Single-holdout metrics (supporting detail, not the headline)"):
            st.dataframe(data["forecast_metrics"], width="stretch", hide_index=True)

with tab_hier:
    section_header("Hierarchical Forecast", "National forecast reconciled down to state and top-25-county level.")

    if hier_summary is not None:
        c1, c2, c3 = st.columns(3)
        c1.metric("National 3-month forecast", whole(hier_summary["national_forecast_total_next_3m"]))
        c2.metric("States beating naive baseline", pct(hier_summary["pct_states_beating_naive"]))
        c3.metric("Top counties beating naive baseline", pct(hier_summary["pct_top_counties_beating_naive"]))
        st.markdown(
            f"""<div class="caveat-box">{hier_summary['note']}</div>""",
            unsafe_allow_html=True,
        )

    left, right = st.columns(2)
    with left:
        if data["hier_state"] is not None:
            hs = data["hier_state"].nlargest(15, "reconciled_forecast_total_next_3m").sort_values("reconciled_forecast_total_next_3m")
            colors = [PALETTE["green"] if b else PALETTE["red"] for b in hs["beats_naive"]]
            fig = go.Figure(go.Bar(
                x=hs["reconciled_forecast_total_next_3m"] / 1e6, y=hs["state"], orientation="h",
                marker_color=colors, text=(hs["reconciled_forecast_total_next_3m"] / 1e6).round(1).astype(str) + "M",
                textposition="outside",
            ))
            fig = clean_layout(fig, height=520)
            fig.update_layout(title="Top 15 States: Next-3-Month Forecast", xaxis_title="Member-months (millions)", showlegend=False)
            st.plotly_chart(fig, width="stretch")
        else:
            missing_notice("hierarchical_state_forecast.csv")
    with right:
        if data["hier_county"] is not None:
            hc = data["hier_county"].nlargest(15, "forecast_total_next_3m").sort_values("forecast_total_next_3m")
            labels = hc["county"] + ", " + hc["state"]
            colors = [PALETTE["green"] if b else PALETTE["red"] for b in hc["beats_naive"]]
            fig = go.Figure(go.Bar(
                x=hc["forecast_total_next_3m"] / 1e6, y=labels, orientation="h",
                marker_color=colors, text=(hc["forecast_total_next_3m"] / 1e6).round(2).astype(str) + "M",
                textposition="outside",
            ))
            fig = clean_layout(fig, height=520)
            fig.update_layout(title="Top 15 Counties: Next-3-Month Forecast", xaxis_title="Member-months (millions)", showlegend=False)
            st.plotly_chart(fig, width="stretch")
        else:
            missing_notice("hierarchical_county_forecast.csv")

    st.caption("Green = the state/county's own linear-drift forecast beats a naive baseline on backtesting; red = treat as directional only.")

    if data["hier_state"] is not None:
        with st.expander("Full state forecast table"):
            st.dataframe(data["hier_state"].sort_values("reconciled_forecast_total_next_3m", ascending=False).head(top_n), width="stretch", hide_index=True)
            st.download_button("Download state forecast", data=csv_bytes(data["hier_state"]), file_name="hierarchical_state_forecast.csv", mime="text/csv")

with tab_growth:
    section_header("Growth Opportunity Ranking", "Markets ranked on growth, scale, and penetration headroom \u2014 sensitivity-tested.")

    if data["state_opp"] is not None:
        state_opp = data["state_opp"].copy()
        state_opp["state_name"] = state_opp["state"].map(STATE_NAME).fillna(state_opp["state"])

        c1, c2, c3 = st.columns(3)
        c1.metric("National growth since first month", pct(national_growth_pct), f"+{whole(national_growth)}")
        c2.metric("Top state", state_opp.iloc[0]["state"], f"score {state_opp.iloc[0]['opportunity_score']:.1f}")
        if data["county_opp"] is not None:
            top_c = data["county_opp"].iloc[0]
            c3.metric("Top county", f"{top_c['county']}, {top_c['state']}", f"score {top_c['opportunity_score']:.1f}")

        map_data = state_opp[state_opp["state"].isin(STATE_NAME)]
        fig = px.choropleth(
            map_data, locations="state", locationmode="USA-states", color="opportunity_score",
            scope="usa", hover_name="state_name",
            hover_data={"growth_pct": ":.2%", "last_enrollment": ":,.0f", "ma_penetration": ":.2%", "state": False},
            color_continuous_scale="Blues", title="State Opportunity Score Heatmap",
        )
        fig = clean_layout(fig, height=480)
        fig.update_geos(bgcolor="white")
        st.plotly_chart(fig, width="stretch")

        left, right = st.columns(2)
        with left:
            fig = px.scatter(
                state_opp, x="last_enrollment", y="growth_pct", size=state_opp["opportunity_score"].clip(lower=1),
                color="ma_penetration", hover_name="state_name", color_continuous_scale="Blues",
                title="Market Scale vs. Growth (color = MA penetration)",
            )
            fig = clean_layout(fig, height=400)
            st.plotly_chart(fig, width="stretch")
        with right:
            top15 = state_opp.nlargest(15, "opportunity_score").sort_values("opportunity_score")
            fig = go.Figure(go.Bar(
                x=top15["opportunity_score"], y=top15["state"], orientation="h",
                marker_color=PALETTE["purple"], text=top15["opportunity_score"].round(1), textposition="outside",
            ))
            fig = clean_layout(fig, height=400)
            fig.update_layout(title="Top 15 States by Opportunity Score", showlegend=False)
            st.plotly_chart(fig, width="stretch")

        if data["opp_sensitivity_state"] is not None:
            with st.expander("Sensitivity check: does the ranking hold under different weights?"):
                st.dataframe(data["opp_sensitivity_state"], width="stretch", hide_index=True)
                st.caption("top10_overlap_pct = share of the current top-10 states that stay in the top-10 under an alternate weighting scheme.")

        left, right = st.columns(2)
        with left:
            st.markdown(f"**Top {top_n} state markets**")
            st.dataframe(
                state_opp[["state", "state_name", "opportunity_score", "last_enrollment", "growth_pct", "ma_penetration", "recommendation"]].head(top_n),
                width="stretch", hide_index=True,
            )
        with right:
            if data["county_opp"] is not None:
                st.markdown(f"**Top {top_n} county markets**")
                st.dataframe(
                    data["county_opp"][["state", "county", "opportunity_score", "last_enrollment", "growth_pct", "ma_penetration", "recommendation"]].head(top_n),
                    width="stretch", hide_index=True,
                )
        st.download_button("Download state opportunity report", data=csv_bytes(state_opp), file_name="state_opportunity_report.csv", mime="text/csv")
    else:
        missing_notice("dashboard_state_opportunities.csv")

with tab_payer:
    section_header("Payer Scorecard", "Which payer to prioritize \u2014 growth, scale, and member-weighted PA burden combined.")

    if data["payer_ranked"] is not None:
        payers = data["payer_ranked"].copy()
        c1, c2, c3 = st.columns(3)
        c1.metric("Payers eligible for ranking", whole(len(payers)))
        c2.metric("Top payer", payers.iloc[0]["parent_organization"][:24], f"score {payers.iloc[0]['priority_score']:.1f}")
        c3.metric("Top payer growth", pct(payers.iloc[0]["growth_pct"]))

        top20 = payers.nlargest(20, "enrolled_latest")
        sizes = (top20["enrolled_latest"] / top20["enrolled_latest"].max()) * 45 + 8
        fig = px.scatter(
            top20, x="growth_pct", y="high_exposure_member_share", size=sizes, color="priority_score",
            hover_name="parent_organization", color_continuous_scale="Viridis",
            labels={"growth_pct": "Enrollment growth %", "high_exposure_member_share": "High-PA-exposure member share"},
            title="Payer Growth vs. PA Burden (bubble size = current members, top 20 by enrollment)",
        )
        fig = clean_layout(fig, height=480)
        st.plotly_chart(fig, width="stretch")

        st.markdown(f"**Top {top_n} payers by priority score**")
        display_cols = ["parent_organization", "priority_score", "enrolled_first", "enrolled_latest", "growth_pct", "high_exposure_member_share", "pa_match_rate"]
        st.dataframe(
            payers[display_cols].head(top_n).rename(columns={
                "parent_organization": "Payer", "priority_score": "Priority Score",
                "enrolled_first": "Members (first month)", "enrolled_latest": "Members (latest)",
                "growth_pct": "Growth %", "high_exposure_member_share": "High-PA Share", "pa_match_rate": "PA Match Rate",
            }),
            width="stretch", hide_index=True,
        )
        st.caption("Ranking requires \u2265 5,000 members at both snapshots and \u2265 50% PA-score match to CPSC enrollment. Excluded payers remain in the full export below.")
        st.download_button("Download full payer scorecard", data=csv_bytes(data["payer_full"] if data["payer_full"] is not None else payers), file_name="payer_scorecard_full.csv", mime="text/csv")
    else:
        missing_notice("payer_scorecard_ranked.csv")

with tab_pa:
    section_header("Prior Authorization Exposure", "CMS PBP benefit-field exposure, weighted by actual member enrollment.")

    if data["pa_metrics"] is not None:
        pm = data["pa_metrics"].iloc[0]
        c1, c2, c3 = st.columns(3)
        c1.metric("Plans reviewed", whole(pm["plans_reviewed"]))
        c2.metric("Plans requiring PA", whole(pm["plans_with_prior_auth_required"]))
        c3.metric("High-exposure plans", whole(pm["high_exposure_plans"]))

    if data["pa_members_national"] is not None:
        pan = data["pa_members_national"].set_index("risk_bucket").reindex(["low", "medium", "high"]).reset_index()
        fig = go.Figure(go.Bar(
            x=pan["risk_bucket"].str.title(), y=pan["member_share"] * 100,
            marker_color=[RISK_COLORS[b] for b in pan["risk_bucket"]],
            text=(pan["member_share"] * 100).round(1).astype(str) + "%", textposition="outside",
        ))
        fig = clean_layout(fig, height=380)
        fig.update_layout(title="Share of MA Members by PA Exposure (Member-Weighted)", yaxis_title="% of matched members", showlegend=False)
        st.plotly_chart(fig, width="stretch")
        st.caption(f"Match rate to CPSC enrollment: {pan['match_rate'].iloc[0]:.1%}. This is member-weighted, not a count of plans.")
    else:
        missing_notice("pa_exposure_by_members_national.csv")

    if data["pa_plans"] is not None:
        pa_plans = data["pa_plans"]
        filtered_pa = pa_plans[pa_plans["risk_bucket"].isin(pa_bucket_filter)].copy()
        left, right = st.columns(2)
        with left:
            fig = px.histogram(
                filtered_pa, x="prior_auth_exposure_score", color="risk_bucket",
                color_discrete_map=RISK_COLORS, title="Plan-Level PA Exposure Score Distribution",
            )
            fig = clean_layout(fig, height=380)
            st.plotly_chart(fig, width="stretch")
        with right:
            by_type = (
                filtered_pa.groupby(["plan_type", "risk_bucket"], as_index=False)
                .agg(avg_exposure=("prior_auth_exposure_score", "mean"), plans=("prior_auth_exposure_score", "size"))
                .sort_values("avg_exposure", ascending=False)
            )
            fig = px.bar(
                by_type.head(15), x="plan_type", y="avg_exposure", color="risk_bucket",
                color_discrete_map=RISK_COLORS, title="Average PA Exposure by Plan Type",
            )
            fig = clean_layout(fig, height=380)
            st.plotly_chart(fig, width="stretch")

        st.markdown("**Prioritization queue**")
        queue_cols = ["contract_id", "plan_id", "organization", "plan_name", "plan_type", "total_auth_category_count", "prior_auth_exposure_score", "risk_bucket", "recommendation"]
        queue = filtered_pa.sort_values("prior_auth_exposure_score", ascending=False)[queue_cols].head(top_n)
        st.dataframe(queue, width="stretch", hide_index=True)
        st.download_button("Download PA prioritization queue", data=csv_bytes(filtered_pa.sort_values("prior_auth_exposure_score", ascending=False)), file_name="pa_prioritization_queue.csv", mime="text/csv")

    st.markdown('<div class="caveat-box">Public CMS files contain no request-level approval/denial outcomes. This is a rule-based exposure signal from CMS PBP benefit fields, not a supervised denial predictor.</div>', unsafe_allow_html=True)

with tab_revenue:
    section_header("Proxy Revenue", "Enrollment forecast converted to a dollar range using a public PMPM assumption \u2014 labeled as a proxy.")

    if data["proxy_revenue"] is not None:
        rev = data["proxy_revenue"]
        x_labels = ["low", "base", "high"]
        full = rev[rev["basis"] == "full_national_reconciled_forecast"].set_index("scenario").loc[x_labels]
        reliable = rev[rev["basis"] == "reliable_states_only_beats_naive"].set_index("scenario").loc[x_labels]

        c1, c2, c3 = st.columns(3)
        c1.metric("Base case, full national forecast", money(full.loc["base", "proxy_revenue_next_3m"]))
        c2.metric("Base case, reliable states only", money(reliable.loc["base", "proxy_revenue_next_3m"]))
        c3.metric("PMPM assumption (base)", f"${int(full.loc['base', 'pmpm_assumption'])}/member/month")

        fig = go.Figure()
        fig.add_trace(go.Bar(x=[s.title() for s in x_labels], y=full["proxy_revenue_next_3m"] / 1e9, name="Full national forecast", marker_color=PALETTE["blue"], text=(full["proxy_revenue_next_3m"] / 1e9).round(0).astype(int).astype(str) + "B", textposition="outside"))
        fig.add_trace(go.Bar(x=[s.title() for s in x_labels], y=reliable["proxy_revenue_next_3m"] / 1e9, name="Reliable states only", marker_color=PALETTE["green"], text=(reliable["proxy_revenue_next_3m"] / 1e9).round(0).astype(int).astype(str) + "B", textposition="outside"))
        fig = clean_layout(fig, height=420)
        fig.update_layout(title="Proxy Revenue Scenarios, Next 3 Months ($ Billions)", barmode="group", yaxis_title="$ Billions")
        st.plotly_chart(fig, width="stretch")

        st.markdown(f'<div class="caveat-box">{rev["pmpm_source_note"].iloc[0]}</div>', unsafe_allow_html=True)
        st.download_button("Download proxy revenue scenarios", data=csv_bytes(rev), file_name="proxy_revenue_scenarios.csv", mime="text/csv")
    else:
        missing_notice("proxy_revenue_scenarios.csv")

with tab_validation:
    section_header("Validation & Methodology", "Automated checks confirming the analysis is scoped and validated correctly.")

    if data["validation"] is not None:
        validation = data["validation"]
        n_fail = (validation["status"] == "fail").sum()
        n_pass = (validation["status"] == "pass").sum()
        c1, c2 = st.columns(2)
        c1.metric("Checks passed", f"{n_pass} / {len(validation)}")
        c2.metric("Checks failed", n_fail)

        def _row_color(status):
            return {"pass": "background-color: #EAF7EE", "fail": "background-color: #FDECEA", "warn": "background-color: #FEF8EC"}.get(status, "")

        st.dataframe(
            validation.style.apply(lambda row: [_row_color(row["status"])] * len(row), axis=1),
            width="stretch", hide_index=True,
        )
        st.download_button("Download validation summary", data=csv_bytes(validation), file_name="model_validation_summary.csv", mime="text/csv")
    else:
        missing_notice("model_validation_summary.csv")

    left, right = st.columns(2)
    with left:
        st.markdown("**Data handling policy**")
        st.write("- CMS-suppressed enrollment values are reported as a [low, high] range, never dropped or zero-filled.")
        st.write("- Growth is computed on a balanced panel (entities numeric in every period) to avoid suppression-driven fake growth.")
        st.write("- County-level merges use FIPS codes, not state+county name text matching.")
    with right:
        st.markdown("**Scope guardrails**")
        st.write("- Forecast reliability is judged against a naive baseline on the same multi-step horizon, not a fixed threshold.")
        st.write("- PA and payer scores are CMS benefit-field exposure signals, not supervised denial predictions.")
        st.write("- Revenue is a labeled proxy from a public national PMPM assumption, not a per-county CMS ratebook.")
