"""Animated architecture diagram, v2: smooth eased motion, glowing pulse
trail, soft drop-shadows, and a subtle "pop" when each stage lights up.
Kept to 7 high-level stages so it reads cleanly instead of looking
crowded.

Produces reports/figures/architecture_animated.gif.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.animation import FuncAnimation, PillowWriter

from src.config import TABLE_DIR

FIG_DIR = TABLE_DIR.parent / "figures"

PALETTE = {
    "blue": "#2E5EAA", "green": "#2E8B57", "orange": "#D98E04",
    "purple": "#6A4C93", "red": "#C0392B",
}
DIM_EDGE = "#DDE1E7"
DIM_TEXT = "#A3AAB5"
ON_TEXT = "#1F2937"
BG_OFF = "#FBFCFD"
SHADOW = "#E9ECEF"

STAGES = [
    ("Public CMS Data", "4 sources: SCP, CPSC,\nPBP, Penetration", PALETTE["blue"]),
    ("Suppression-Aware\nProcessing", "[low, high] bounds,\nbalanced-panel growth", PALETTE["orange"]),
    ("Validated\nForecasting", "15-split rolling backtest\nvs. naive baseline", PALETTE["green"]),
    ("Growth & PA\nScoring", "FIPS-merged, member-\nweighted, sensitivity-tested", PALETTE["green"]),
    ("Payer & Hierarchical\nIntelligence", "Payer scorecard,\nstate/county reconciled", PALETTE["purple"]),
    ("Proxy Revenue &\nValidation", "Scenario-based, 6\nautomated checks", PALETTE["purple"]),
    ("Interactive\nDashboard", "Streamlit, live\nfiltering & exports", PALETTE["red"]),
]

N = len(STAGES)
X = [i * 2.0 for i in range(N)]
Y = 0.0
BOX_W, BOX_H = 1.7, 0.95


def ease_in_out(t: float) -> float:
    return t * t * (3 - 2 * t)


def tint(hex_color: str, alpha: float = 0.14) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    r = int(r + (255 - r) * (1 - alpha))
    g = int(g + (255 - g) * (1 - alpha))
    b = int(b + (255 - b) * (1 - alpha))
    return f"#{r:02X}{g:02X}{b:02X}"


def build_figure():
    fig, ax = plt.subplots(figsize=(15.5, 4.4))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.set_xlim(-1.1, X[-1] + 1.1)
    ax.set_ylim(-2.0, 1.6)
    ax.axis("off")

    shadows, boxes = [], []
    for i, (title, sub, color) in enumerate(STAGES):
        shadow = mpatches.FancyBboxPatch(
            (X[i] - BOX_W / 2 + 0.045, Y - BOX_H / 2 - 0.05), BOX_W, BOX_H,
            boxstyle="round,pad=0.02,rounding_size=0.12",
            linewidth=0, facecolor=SHADOW, zorder=2, alpha=0.7,
        )
        ax.add_patch(shadow)
        shadows.append(shadow)

        glow = mpatches.FancyBboxPatch(
            (X[i] - BOX_W / 2 - 0.06, Y - BOX_H / 2 - 0.06), BOX_W + 0.12, BOX_H + 0.12,
            boxstyle="round,pad=0.02,rounding_size=0.16",
            linewidth=0, facecolor=color, zorder=2, alpha=0.0,
        )
        ax.add_patch(glow)

        box = mpatches.FancyBboxPatch(
            (X[i] - BOX_W / 2, Y - BOX_H / 2), BOX_W, BOX_H,
            boxstyle="round,pad=0.02,rounding_size=0.12",
            linewidth=1.8, edgecolor=DIM_EDGE, facecolor=BG_OFF, zorder=3,
        )
        ax.add_patch(box)
        title_txt = ax.text(X[i], Y + 0.16, title, ha="center", va="center",
                             fontsize=10.5, color=DIM_TEXT, fontweight="normal", zorder=4)
        sub_txt = ax.text(X[i], Y - 0.28, sub, ha="center", va="center",
                           fontsize=7.6, color=DIM_TEXT, zorder=4)
        badge = ax.text(X[i], Y + BOX_H / 2 + 0.30, f"{i + 1}", ha="center", va="center",
                         fontsize=10, color="white", fontweight="bold", zorder=5,
                         bbox=dict(boxstyle="circle,pad=0.34", facecolor=DIM_EDGE, edgecolor="none"))
        boxes.append(dict(box=box, glow=glow, title=title_txt, sub=sub_txt, badge=badge, color=color))

    lines = []
    for i in range(N - 1):
        line, = ax.plot([X[i] + BOX_W / 2, X[i + 1] - BOX_W / 2], [Y, Y],
                         color=DIM_EDGE, linewidth=2.4, zorder=1, solid_capstyle="round")
        lines.append(line)

    trail = [ax.scatter([], [], s=0, color=PALETTE["blue"], zorder=6, linewidths=0) for _ in range(6)]
    pulse = ax.scatter([X[0]], [Y], s=0, color=PALETTE["blue"], zorder=7,
                        edgecolors="white", linewidths=1.4)
    caption = ax.text((X[0] + X[-1]) / 2, -1.55, "", ha="center", va="center",
                       fontsize=11.5, color="#4B5563", style="italic")
    banner = ax.text((X[0] + X[-1]) / 2, 1.35, "RCM Intelligence \u2014 End-to-End Pipeline",
                      ha="center", va="center", fontsize=13, color="#111827", fontweight="bold")

    fig.tight_layout()
    return fig, ax, boxes, lines, pulse, trail, caption


CAPTIONS = [
    "Ingesting four public CMS Medicare Advantage datasets...",
    "Building suppression-aware bounds and balanced-panel growth...",
    "Backtesting forecasts across 15 rolling-origin splits...",
    "Scoring growth opportunity and prior-authorization exposure...",
    "Ranking payers and reconciling the state/county forecast...",
    "Converting to proxy revenue scenarios and running validation...",
    "Serving every result in the interactive dashboard.",
]

TRAVEL_FRAMES = 16
HOLD_FRAMES = 10
POP_FRAMES = 6


def make_animation():
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig, ax, boxes, lines, pulse, trail, caption = build_figure()

    lit = set()
    popping = {}

    def reset_all():
        lit.clear()
        popping.clear()
        for b in boxes:
            b["box"].set_edgecolor(DIM_EDGE)
            b["box"].set_linewidth(1.8)
            b["box"].set_facecolor(BG_OFF)
            b["glow"].set_alpha(0.0)
            b["title"].set_color(DIM_TEXT)
            b["title"].set_fontweight("normal")
            b["sub"].set_color(DIM_TEXT)
            b["badge"].get_bbox_patch().set_facecolor(DIM_EDGE)
        for line in lines:
            line.set_color(DIM_EDGE)
            line.set_linewidth(2.4)
        for t in trail:
            t.set_sizes([0])

    def light_up(i, pop_frame):
        lit.add(i)
        b = boxes[i]
        b["box"].set_edgecolor(b["color"])
        b["box"].set_linewidth(2.8)
        b["box"].set_facecolor(tint(b["color"]))
        b["title"].set_color(ON_TEXT)
        b["title"].set_fontweight("bold")
        b["sub"].set_color("#4B5563")
        b["badge"].get_bbox_patch().set_facecolor(b["color"])
        pop_t = min(pop_frame / POP_FRAMES, 1.0)
        glow_alpha = (1 - abs(pop_t - 0.5) * 2) * 0.22
        b["glow"].set_alpha(max(glow_alpha, 0.05) if pop_t < 1.0 else 0.06)

    per_stage = TRAVEL_FRAMES + HOLD_FRAMES
    total_frames = per_stage * N + 22

    def update(frame):
        f = frame % (total_frames + 14)
        if f == 0:
            reset_all()
            caption.set_text("")
            pulse.set_sizes([0])

        if f >= total_frames:
            pulse.set_sizes([0])
            for t in trail:
                t.set_sizes([0])
            caption.set_text("\u2713 Pipeline complete \u2014 6 of 6 validation checks passing.")
            return []

        stage_idx = min(f // per_stage, N - 1)
        within = f % per_stage

        if within < TRAVEL_FRAMES and stage_idx > 0:
            t_lin = within / TRAVEL_FRAMES
            t = ease_in_out(t_lin)
            x0, x1 = X[stage_idx - 1] + BOX_W / 2, X[stage_idx] - BOX_W / 2
            cx = x0 + (x1 - x0) * t
            pulse.set_offsets([[cx, Y]])
            pulse.set_sizes([160])
            for k, tdot in enumerate(trail):
                lag = (within - (k + 1) * 2) / TRAVEL_FRAMES
                if lag > 0:
                    tx = x0 + (x1 - x0) * ease_in_out(min(lag, 1.0))
                    tdot.set_offsets([[tx, Y]])
                    tdot.set_sizes([90 - k * 12])
                    tdot.set_alpha(max(0.5 - k * 0.08, 0.05))
                else:
                    tdot.set_sizes([0])
            lines[stage_idx - 1].set_color(PALETTE["blue"])
            lines[stage_idx - 1].set_linewidth(3.2)
            caption.set_text(CAPTIONS[stage_idx - 1])
        else:
            pop_frame = within - TRAVEL_FRAMES if within >= TRAVEL_FRAMES else HOLD_FRAMES
            light_up(stage_idx, pop_frame)
            pulse.set_sizes([0])
            for t in trail:
                t.set_sizes([0])
            caption.set_text(CAPTIONS[stage_idx])

        return []

    anim = FuncAnimation(fig, update, frames=total_frames + 40, interval=90, blit=False)
    out_path = FIG_DIR / "architecture_animated.gif"
    anim.save(str(out_path), writer=PillowWriter(fps=1000 / 90))
    plt.close(fig)
    print(f"Saved animated architecture diagram: {out_path}")


def main() -> None:
    make_animation()


if __name__ == "__main__":
    main()
