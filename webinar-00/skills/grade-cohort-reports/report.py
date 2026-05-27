#!/usr/bin/env python3
"""Generate a PDF cohort report from grade-cohort-reports outputs.

Reads:
    <grade-dir>/raw/<agent_id>.json   # per-agent strict-JSON scorecards

Writes:
    <grade-dir>/cohort.pdf            # 4-page PDF
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.patches import Patch
import numpy as np


PAGE_LANDSCAPE = (11.0, 8.5)
PAGE_PORTRAIT  = (8.5, 11.0)


def load_cards(grade_dir: Path) -> list[dict]:
    raw_dir = grade_dir / "raw"
    if not raw_dir.is_dir():
        sys.exit(f"report: missing {raw_dir}")
    cards = []
    for f in sorted(raw_dir.glob("*.json")):
        try:
            cards.append(json.loads(f.read_text()))
        except json.JSONDecodeError as e:
            print(f"report: WARN — {f.name} not parseable: {e}", file=sys.stderr)
    if not cards:
        sys.exit("report: no parseable scorecards")
    # alphabetical by agent_id, stable.
    cards.sort(key=lambda c: c["agent_id"])
    return cards


def fig_summary(cards: list[dict]) -> plt.Figure:
    """Cover page — single-column text block with proper margins."""
    n = len(cards)
    vals = [(c.get("headline", {}) or {}).get("improvement_pct_numeric") or 0.0 for c in cards]
    canonical_vals = [
        (c.get("headline", {}) or {}).get("improvement_pct_numeric") or 0.0
        for c in cards
        if (c.get("headline", {}) or {}).get("comparable_to_canonical") is True
    ]
    n_canonical = len(canonical_vals)
    n_flagged = n - n_canonical
    median_all = float(np.median(vals)) if vals else 0.0
    median_canon = float(np.median(canonical_vals)) if canonical_vals else 0.0
    lo, hi = (min(vals), max(vals)) if vals else (0, 0)

    fig = plt.figure(figsize=PAGE_PORTRAIT)
    fig.subplots_adjust(left=0.08, right=0.92, top=0.92, bottom=0.08)
    ax = fig.add_subplot(111)
    ax.axis("off")

    title = "Cohort grading report"
    subtitle = f"{n} agents · alphabetical order throughout"

    ax.text(0.0, 1.00, title, transform=ax.transAxes,
            fontsize=22, fontweight="bold", va="top")
    ax.text(0.0, 0.95, subtitle, transform=ax.transAxes,
            fontsize=11, color="#555", va="top")

    # Stats table
    rows = [
        ("Canonical platform / measured truth", f"{n_canonical} / {n}"),
        ("Non-canonical / flagged",              f"{n_flagged} / {n}"),
        ("",                                     ""),
        ("Median improvement (all)",             f"{median_all:+.1f} %"),
        ("Median improvement (canonical only)",  f"{median_canon:+.1f} %"),
        ("Range across cohort",                  f"{lo:+.1f} %  …  {hi:+.1f} %"),
    ]
    y = 0.85
    for k, v in rows:
        ax.text(0.0,  y, k, transform=ax.transAxes, fontsize=11, va="top")
        ax.text(0.55, y, v, transform=ax.transAxes, fontsize=11, va="top",
                family="monospace")
        y -= 0.04

    # Pages
    ax.text(0.0, 0.55, "Contents", transform=ax.transAxes,
            fontsize=14, fontweight="bold", va="top")
    pages = [
        "Page 2 — Outcome bars: per-agent % improvement on the primary metric",
        "Page 3 — Attribution: what each agent credits for the improvement",
        "Page 4 — Methodology rubric heatmap (agents × rubric items)",
    ]
    y = 0.50
    for line in pages:
        ax.text(0.02, y, line, transform=ax.transAxes, fontsize=10, va="top")
        y -= 0.035

    # Caveats
    ax.text(0.0, 0.36, "Caveats", transform=ax.transAxes,
            fontsize=14, fontweight="bold", va="top")
    cavs = [
        "Improvement % is self-reported on the agent's chosen metric and unit.",
        "Different agents picked rad/s, mrad/s, deg/s, °/s on different masks and splits.",
        "Relative % is the only universally comparable axis; absolute values are not.",
        "",
        "A non-canonical bar (grey) means the agent scored on a non-canonical platform",
        "OR substituted a fabricated proxy for the measured truth channel. Its number",
        "is not directly comparable to canonical bars.",
    ]
    y = 0.31
    for line in cavs:
        ax.text(0.02, y, line, transform=ax.transAxes, fontsize=9.5, va="top", color="#333")
        y -= 0.028

    return fig


def fig_outcome(cards: list[dict]) -> plt.Figure:
    """Horizontal bar: % improvement, alphabetical, % label inside bar end,
    metric unit under the agent name, top contributor in a small side column.
    """
    labels = [c["agent_id"] for c in cards]
    vals = [(c.get("headline", {}) or {}).get("improvement_pct_numeric") or 0.0 for c in cards]
    units = [(c.get("headline", {}) or {}).get("unit_normalized") or "?" for c in cards]
    canonical = [(c.get("headline", {}) or {}).get("comparable_to_canonical") for c in cards]
    top = [(c.get("headline", {}) or {}).get("top_contributor") or "" for c in cards]

    fig = plt.figure(figsize=PAGE_LANDSCAPE)
    fig.subplots_adjust(left=0.16, right=0.96, top=0.90, bottom=0.10)
    ax = fig.add_subplot(111)

    y = np.arange(len(cards))
    colours = ["#2a7ae2" if c else "#9a9a9a" for c in canonical]
    bars = ax.barh(y, vals, color=colours, edgecolor="black", linewidth=0.5, height=0.7)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("Self-reported improvement on primary metric (%)")
    ax.set_title("Outcome — improvement on the lateral metric (alphabetical)",
                 fontsize=13, pad=14)
    ax.axvline(0, color="k", linewidth=0.5)
    ax.grid(True, axis="x", alpha=0.3)

    # % labels just right of each bar; top contributor on a separate right column.
    max_v = max(vals) if vals else 1.0
    ax.set_xlim(0, max_v * 1.55)
    for i, (v, u, t) in enumerate(zip(vals, units, top)):
        ax.text(v + max_v * 0.01, i, f"{v:+.1f}%", va="center", ha="left",
                fontsize=10, fontweight="bold")
        ax.text(max_v * 1.20, i, f"unit: {u}",
                va="center", ha="left", fontsize=9, color="#444",
                family="monospace")
    # Side legend
    ax.legend(handles=[
        Patch(facecolor="#2a7ae2", edgecolor="black", label="canonical platform"),
        Patch(facecolor="#9a9a9a", edgecolor="black", label="non-canonical / flagged"),
    ], loc="lower right", fontsize=9, framealpha=0.95)

    # subtitle below title noting top contributors are on page 3
    ax.text(0.5, 1.01,
            "Top contributor per agent is shown on page 3 (attribution breakdown).",
            transform=ax.transAxes, ha="center", fontsize=9, color="#555")
    return fig


def fig_attribution(cards: list[dict]) -> plt.Figure:
    """Stacked horizontal bar per agent, alphabetical. Variant chunks labelled
    only when wide enough; small chunks get a small marker without text overlap.
    """
    fig = plt.figure(figsize=PAGE_LANDSCAPE)
    fig.subplots_adjust(left=0.14, right=0.96, top=0.90, bottom=0.10)
    ax = fig.add_subplot(111)
    y = np.arange(len(cards))
    cmap = plt.get_cmap("tab20")
    label_min_width = 8.0  # only label chunks this wide (%)

    for i, card in enumerate(cards):
        ab = card.get("attribution_breakdown", []) or []
        left_pos = 0.0
        left_neg = 0.0
        for j, v in enumerate(ab):
            pct = v.get("contribution_pct")
            if pct is None:
                continue
            color = cmap(j % 20)
            name = v.get("variant_name", "?")
            short = (name[:22] + "…") if len(name) > 23 else name
            if pct >= 0:
                ax.barh(i, pct, left=left_pos, color=color,
                        edgecolor="black", linewidth=0.4, height=0.7)
                if pct >= label_min_width:
                    ax.text(left_pos + pct / 2, i,
                            f"{short}\n{pct:.1f}%",
                            ha="center", va="center", fontsize=8, color="black")
                left_pos += pct
            else:
                left_neg += pct
                ax.barh(i, pct, left=left_neg - pct, color=color,
                        edgecolor="black", linewidth=0.4, height=0.7)
                if abs(pct) >= label_min_width:
                    ax.text(left_neg - pct / 2, i,
                            f"{short}\n{pct:.1f}%",
                            ha="center", va="center", fontsize=8, color="black")

    ax.set_yticks(y)
    ax.set_yticklabels([c["agent_id"] for c in cards], fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("% of total improvement attributed to each variant (agent's own scheme)")
    ax.set_title("Attribution breakdown — variant contributions per agent (alphabetical)",
                 fontsize=13, pad=14)
    ax.axvline(0, color="k", linewidth=0.5)
    ax.set_xlim(-25, 110)
    ax.grid(True, axis="x", alpha=0.3)
    return fig


def fig_rubric_heatmap(cards: list[dict]) -> plt.Figure:
    """Methodology rubric heatmap — pcolormesh avoids the imshow gap artefact."""
    item_ids = []
    for c in cards:
        for it in c.get("items", []):
            if it["id"] not in item_ids:
                item_ids.append(it["id"])

    grid = np.full((len(cards), len(item_ids)), np.nan)
    for r, c in enumerate(cards):
        idx = {it["id"]: it for it in c.get("items", [])}
        for col, rid in enumerate(item_ids):
            it = idx.get(rid)
            if it is None:
                continue
            res = it.get("result")
            if res is True:
                grid[r, col] = 1
            elif res is False:
                grid[r, col] = 0
            else:
                grid[r, col] = -1

    fig = plt.figure(figsize=PAGE_LANDSCAPE)
    fig.subplots_adjust(left=0.14, right=0.96, top=0.88, bottom=0.18)
    ax = fig.add_subplot(111)

    cmap = matplotlib.colors.ListedColormap(["#cccccc", "#d9534f", "#5cb85c"])
    bounds = [-1.5, -0.5, 0.5, 1.5]
    norm = matplotlib.colors.BoundaryNorm(bounds, cmap.N)

    nr, nc = grid.shape
    X = np.arange(nc + 1)
    Y = np.arange(nr + 1)
    ax.pcolormesh(X, Y, grid, cmap=cmap, norm=norm, edgecolors="white", linewidth=2)

    for r in range(nr):
        for col in range(nc):
            v = grid[r, col]
            sym = {1: "✓", 0: "✗", -1: "—"}.get(int(v) if not np.isnan(v) else -99, "?")
            ax.text(col + 0.5, r + 0.5, sym, ha="center", va="center",
                    color="white", fontsize=14, fontweight="bold")

    ax.set_xticks(np.arange(nc) + 0.5)
    ax.set_xticklabels(item_ids, rotation=25, ha="right", fontsize=9)
    ax.set_yticks(np.arange(nr) + 0.5)
    ax.set_yticklabels([c["agent_id"] for c in cards], fontsize=10)
    ax.invert_yaxis()
    ax.set_xlim(0, nc)
    ax.set_ylim(nr, 0)
    ax.set_title("Methodology rubric — green ✓ pass · red ✗ fail · grey — null / not addressed",
                 fontsize=13, pad=14)
    # remove tick lines for cleanliness
    ax.tick_params(length=0)
    return fig


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--grade-dir", type=Path, required=True)
    args = p.parse_args()

    cards = load_cards(args.grade_dir)
    pdf_path = args.grade_dir / "cohort.pdf"

    with PdfPages(pdf_path) as pdf:
        pdf.savefig(fig_summary(cards),         bbox_inches="tight")
        pdf.savefig(fig_outcome(cards),         bbox_inches="tight")
        pdf.savefig(fig_attribution(cards),     bbox_inches="tight")
        pdf.savefig(fig_rubric_heatmap(cards),  bbox_inches="tight")

    print(f"cohort PDF: {pdf_path}")


if __name__ == "__main__":
    main()
