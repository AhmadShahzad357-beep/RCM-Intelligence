"""Generate all charts for the project as PNG files under reports/figures/.

Nine charts covering both the original pipeline outputs (enrollment trend,
backtest comparison, growth-by-state, opportunity ranking, PA exposure) and
the three new features (payer scorecard, hierarchical forecast at state and
county level, proxy revenue scenarios).

Style: consistent professional palette, no gridlines, legends placed to
avoid overlapping data or annotations, generous margins so labels never
get clipped.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

from src.config import PROCESSED_DIR, TABLE_DIR, ensure_dirs

FIG_DIR = TABLE_DIR.parent / "figures"

# ---- shared style -----------------------------------------------------
PALETTE = {
    "blue": "#2E5EAA",
    "green": "#2E8B57",
    "orange": "#D98E04",
    "red": "#C0392B",
    "purple": "#6A4C93",
    "gray": "#8C8C8C",
    "teal": "#1B7F79",
}
BG = "#FFFFFF"
TEXT = "#222222"
MUTED = "#666666"

plt.rcParams.update(
    {
        "figure.facecolor": BG,
        "axes.facecolor": BG,
        "axes.edgecolor": "#B0B0B0",
        "axes.labelcolor": TEXT,
        "axes.titlecolor": TEXT,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
        "axes.labelsize": 10.5,
        "axes.grid": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "font.size": 10,
        "font.family": "DejaVu Sans",
        "legend.frameon": False,
        "legend.fontsize": 9,
        "figure.dpi": 150,
    }
)


def _save(fig, name: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / f"{name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"Saved {path}")


def _style_axes(ax) -> None:
    ax.grid(False)
    ax.set_axisbelow(True)


def chart_1_national_trend() -> None:
    national = pd.read_parquet(PROCESSED_DIR / "ma_scp_monthly_national.parquet").sort_values("report_month")
    bounds = pd.read_csv(TABLE_DIR / "ma_scp_national_bounds.csv").sort_values("report_month")
    forecast_total = pd.read_csv(TABLE_DIR / "hierarchical_reconciliation_summary.csv").iloc[0]["national_forecast_total_next_3m"]

    # Normalize both date columns to plain strings -- national comes from
    # parquet (datetime/Period dtype) and bounds comes from CSV (string
    # dtype); plotting both on the same axis without matching types makes
    # matplotlib's date/category converter throw a TypeError.
    national = national.copy()
    bounds = bounds.copy()
    national["report_month"] = national["report_month"].astype(str)
    bounds["report_month"] = bounds["report_month"].astype(str)

    fig, ax = plt.subplots(figsize=(12, 5.5))
    _style_axes(ax)

    ax.fill_between(bounds["report_month"], bounds["enrolled_low"], bounds["enrolled_high"], color=PALETTE["blue"], alpha=0.12, label="Suppression-adjusted range")
    ax.plot(national["report_month"], national["observed_enrollment"], color=PALETTE["blue"], linewidth=2.2, label="Actual (observed)")

    last_month = national["report_month"].iloc[-1]
    last_val = national["observed_enrollment"].iloc[-1]
    ax.scatter([last_month], [last_val], color=PALETTE["red"], zorder=5, s=40, label="Latest observed month")

    ax.set_title("National MA Enrollment: Actual Trend + Suppression-Adjusted Range")
    ax.set_xlabel("Report Month")
    ax.set_ylabel("Enrollment")
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _: f"{x/1e6:.1f}M"))
    ax.tick_params(axis="x", rotation=90, labelsize=8)

    ax.legend(loc="upper left", bbox_to_anchor=(0.0, -0.28), ncol=3)
    ax.text(
        0.99, 0.03,
        f"Next 3-month forecast total: {forecast_total:,.0f} member-months",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=9, color=PALETTE["red"],
        bbox=dict(boxstyle="round,pad=0.35", facecolor="#FDEDEC", edgecolor=PALETTE["red"], linewidth=0.6),
    )
    fig.tight_layout()
    _save(fig, "01_national_enrollment_trend")


def chart_2_backtest_comparison() -> None:
    bt = pd.read_csv(TABLE_DIR / "backtest_summary.csv").sort_values("mean_mase")
    fig, ax = plt.subplots(figsize=(8, 5.5))
    _style_axes(ax)

    colors = [PALETTE["green"] if m == "linear_drift" else PALETTE["gray"] for m in bt["model"]]
    bars = ax.bar(bt["model"], bt["mean_mase"], color=colors, width=0.55)
    ax.axhline(bt["mean_mase"].min(), color=PALETTE["green"], linestyle="--", linewidth=1, alpha=0.6)

    ax.set_title("Rolling-Origin Backtest: Mean MASE by Model")
    ax.set_ylabel("Mean MASE (lower is better, 15 splits)")
    ax.set_ylim(0, bt["mean_mase"].max() * 1.25)

    for bar, v in zip(bars, bt["mean_mase"]):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 0.06, f"{v:.2f}", ha="center", fontsize=9.5, color=TEXT)

    fig.tight_layout()
    _save(fig, "02_backtest_model_comparison")


def chart_3_state_growth() -> None:
    growth = pd.read_csv(TABLE_DIR / "ma_scp_state_growth.csv").dropna(subset=["growth_pct"])
    top15 = growth.nlargest(15, "growth_pct").sort_values("growth_pct")

    fig, ax = plt.subplots(figsize=(9, 7.5))
    _style_axes(ax)

    bars = ax.barh(top15["state"], top15["growth_pct"] * 100, color=PALETTE["orange"], height=0.62)
    ax.set_title("Where Is MA Enrollment Growing Fastest?\nTop 15 States, Balanced Panel")
    ax.set_xlabel("Growth % (first to latest observed month)")
    ax.set_xlim(0, top15["growth_pct"].max() * 100 * 1.18)

    for bar, v in zip(bars, top15["growth_pct"] * 100):
        ax.text(v + 0.4, bar.get_y() + bar.get_height() / 2, f"{v:.1f}%", va="center", fontsize=9, color=TEXT)

    fig.tight_layout()
    _save(fig, "03_state_growth_ranking")


def chart_4_opportunity_ranking() -> None:
    opp = pd.read_csv(TABLE_DIR / "dashboard_state_opportunities.csv").nlargest(10, "opportunity_score")
    opp = opp.sort_values("opportunity_score")

    fig, ax = plt.subplots(figsize=(9, 6.2))
    _style_axes(ax)

    bars = ax.barh(opp["state"], opp["opportunity_score"], color=PALETTE["purple"], height=0.6)
    ax.set_title("Top 10 State Opportunity Scores\n(Growth + Scale + Penetration Headroom)")
    ax.set_xlabel("Opportunity Score (0-100)")
    ax.set_xlim(0, 100)

    for bar, v in zip(bars, opp["opportunity_score"]):
        ax.text(v + 1.2, bar.get_y() + bar.get_height() / 2, f"{v:.1f}", va="center", fontsize=9.5, color=TEXT)

    fig.tight_layout()
    _save(fig, "04_state_opportunity_ranking")


def chart_5_pa_exposure() -> None:
    pa = pd.read_csv(TABLE_DIR / "pa_exposure_by_members_national.csv")
    order = ["low", "medium", "high"]
    pa = pa.set_index("risk_bucket").reindex(order).reset_index()
    colors = {"low": PALETTE["green"], "medium": PALETTE["orange"], "high": PALETTE["red"]}

    fig, ax = plt.subplots(figsize=(7.5, 5.5))
    _style_axes(ax)

    bars = ax.bar(pa["risk_bucket"].str.title(), pa["member_share"] * 100, color=[colors[b] for b in pa["risk_bucket"]], width=0.5)
    ax.set_title("Share of MA Members by Prior-Authorization Exposure\n(Member-Weighted, Not Plan-Count)")
    ax.set_ylabel("% of matched MA members")
    ax.set_ylim(0, max(pa["member_share"] * 100) * 1.25)

    for bar, v in zip(bars, pa["member_share"] * 100):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 1.2, f"{v:.1f}%", ha="center", fontsize=10, color=TEXT)

    fig.tight_layout()
    _save(fig, "05_pa_exposure_by_members")


def chart_6_payer_scorecard() -> None:
    payers = pd.read_csv(TABLE_DIR / "payer_scorecard_ranked.csv").nlargest(20, "enrolled_latest")

    fig, ax = plt.subplots(figsize=(9.5, 7.5))
    _style_axes(ax)

    sizes = (payers["enrolled_latest"] / payers["enrolled_latest"].max()) * 1400 + 40
    sc = ax.scatter(
        payers["growth_pct"] * 100, payers["high_exposure_member_share"] * 100,
        s=sizes, alpha=0.65, c=payers["priority_score"], cmap="viridis", edgecolors="white", linewidths=0.6,
    )

    top_labels = payers.nlargest(6, "priority_score")
    for _, row in top_labels.iterrows():
        ax.annotate(
            row["parent_organization"][:22],
            (row["growth_pct"] * 100, row["high_exposure_member_share"] * 100),
            fontsize=7.5, color=TEXT, xytext=(6, 6), textcoords="offset points",
        )

    ax.set_title("Payer Scorecard: Growth vs. PA Burden\n(Bubble Size = Current Members, Top 20 by Enrollment)")
    ax.set_xlabel("Enrollment Growth %")
    ax.set_ylabel("High-PA-Exposure Member Share %")
    ax.margins(x=0.12, y=0.15)

    cbar = fig.colorbar(sc, ax=ax, pad=0.02)
    cbar.set_label("Priority Score", fontsize=9)
    fig.tight_layout()
    _save(fig, "06_payer_scorecard_scatter")


def chart_7_hierarchical_state() -> None:
    hier = pd.read_csv(TABLE_DIR / "hierarchical_state_forecast.csv").nlargest(15, "reconciled_forecast_total_next_3m")
    hier = hier.sort_values("reconciled_forecast_total_next_3m")

    fig, ax = plt.subplots(figsize=(9, 7.5))
    _style_axes(ax)

    colors = [PALETTE["green"] if b else PALETTE["red"] for b in hier["beats_naive"]]
    bars = ax.barh(hier["state"], hier["reconciled_forecast_total_next_3m"] / 1e6, color=colors, height=0.62)

    ax.set_title("Hierarchical Forecast: Top 15 States, Next 3 Months")
    ax.set_xlabel("Forecast member-months (millions)")
    ax.set_xlim(0, (hier["reconciled_forecast_total_next_3m"] / 1e6).max() * 1.2)

    for bar, v in zip(bars, hier["reconciled_forecast_total_next_3m"] / 1e6):
        ax.text(v + 0.15, bar.get_y() + bar.get_height() / 2, f"{v:.1f}M", va="center", fontsize=8.5, color=TEXT)

    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, color=PALETTE["green"], label="Beats naive baseline"),
        plt.Rectangle((0, 0), 1, 1, color=PALETTE["red"], label="Does not beat naive baseline"),
    ]
    ax.legend(handles=legend_handles, loc="lower right")
    fig.tight_layout()
    _save(fig, "07_hierarchical_state_forecast")


def chart_8_hierarchical_county() -> None:
    hier = pd.read_csv(TABLE_DIR / "hierarchical_county_forecast.csv").nlargest(15, "forecast_total_next_3m")
    hier = hier.sort_values("forecast_total_next_3m")
    labels = hier["county"] + ", " + hier["state"]

    fig, ax = plt.subplots(figsize=(9, 7.5))
    _style_axes(ax)

    colors = [PALETTE["green"] if b else PALETTE["red"] for b in hier["beats_naive"]]
    bars = ax.barh(labels, hier["forecast_total_next_3m"] / 1e6, color=colors, height=0.62)

    ax.set_title("Hierarchical Forecast: Top 15 Counties, Next 3 Months")
    ax.set_xlabel("Forecast member-months (millions)")
    ax.set_xlim(0, (hier["forecast_total_next_3m"] / 1e6).max() * 1.2)

    for bar, v in zip(bars, hier["forecast_total_next_3m"] / 1e6):
        ax.text(v + 0.03, bar.get_y() + bar.get_height() / 2, f"{v:.2f}M", va="center", fontsize=8.5, color=TEXT)

    legend_handles = [
        plt.Rectangle((0, 0), 1, 1, color=PALETTE["green"], label="Beats naive baseline"),
        plt.Rectangle((0, 0), 1, 1, color=PALETTE["red"], label="Does not beat naive baseline"),
    ]
    ax.legend(handles=legend_handles, loc="lower right")
    fig.tight_layout()
    _save(fig, "08_hierarchical_county_forecast")


def chart_9_proxy_revenue() -> None:
    rev = pd.read_csv(TABLE_DIR / "proxy_revenue_scenarios.csv")
    x_labels = ["low", "base", "high"]
    full = rev[rev["basis"] == "full_national_reconciled_forecast"].set_index("scenario").loc[x_labels, "proxy_revenue_next_3m"] / 1e9
    reliable = rev[rev["basis"] == "reliable_states_only_beats_naive"].set_index("scenario").loc[x_labels, "proxy_revenue_next_3m"] / 1e9

    fig, ax = plt.subplots(figsize=(8.5, 5.8))
    _style_axes(ax)

    width = 0.34
    idx = range(len(x_labels))
    bars1 = ax.bar([i - width / 2 for i in idx], full, width, label="Full national forecast", color=PALETTE["blue"])
    bars2 = ax.bar([i + width / 2 for i in idx], reliable, width, label="Reliable states only", color=PALETTE["green"])

    ax.set_xticks(list(idx))
    ax.set_xticklabels([s.title() for s in x_labels])
    ax.set_ylabel("Proxy Revenue, Next 3 Months ($ Billions)")
    ax.set_title("Proxy Revenue Scenarios (PMPM Assumption-Based)")
    ax.set_ylim(0, max(full.max(), reliable.max()) * 1.22)

    for bars in (bars1, bars2):
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h + 2, f"${h:.0f}B", ha="center", fontsize=9, color=TEXT)

    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2)
    fig.tight_layout()
    _save(fig, "09_proxy_revenue_scenarios")


def main() -> None:
    ensure_dirs()
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    chart_1_national_trend()
    chart_2_backtest_comparison()
    chart_3_state_growth()
    chart_4_opportunity_ranking()
    chart_5_pa_exposure()
    chart_6_payer_scorecard()
    chart_7_hierarchical_state()
    chart_8_hierarchical_county()
    chart_9_proxy_revenue()
    print(f"\nAll 9 charts saved to {FIG_DIR}")


if __name__ == "__main__":
    main()
