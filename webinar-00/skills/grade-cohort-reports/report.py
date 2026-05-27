#!/usr/bin/env python3
"""Generate a PDF cohort report from grade-cohort-reports outputs.

Reads:
    <grade-dir>/raw/<agent_id>.json   # per-agent strict-JSON scorecards
    <grade-dir>/cohort.json           # aggregate (from aggregate.py; optional)

Writes:
    <grade-dir>/cohort.pdf            # 3-page PDF: outcome bars + attribution stacks + rubric heatmap

Outcome page is the headline visual the human asked for: how much did each
agent improve the primary metric. Agents on non-canonical platforms / fabricated
truth channels are visually flagged so they don't get falsely compared to
canonical runs.
"""

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np


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
    return cards


def fig_outcome(cards: list[dict]) -> plt.Figure:
    """Horizontal bar: % improvement on the agent's self-reported primary metric.
    Bars for non-comparable agents drawn in a flag colour with a hatch.
    """
    cards = sorted(cards, key=lambda c: (c.get("headline", {}) or {}).get("improvement_pct_numeric") or 0)
    labels = [c["agent_id"] for c in cards]
    vals = [(c.get("headline", {}) or {}).get("improvement_pct_numeric") or 0.0 for c in cards]
    units = [(c.get("headline", {}) or {}).get("unit_normalized") or "?" for c in cards]
    comparable = [(c.get("headline", {}) or {}).get("comparable_to_canonical") for c in cards]
    top = [(c.get("headline", {}) or {}).get("top_contributor") or "" for c in cards]

    fig, ax = plt.subplots(figsize=(8.5, 0.45 * len(cards) + 2.5))
    y = np.arange(len(cards))
    colours = ["#888888" if c is False else "#2a7ae2" for c in comparable]
    hatches = ["//" if c is False else "" for c in comparable]
    bars = ax.barh(y, vals, color=colours, edgecolor="black", linewidth=0.6)
    for b, h in zip(bars, hatches):
        if h:
            b.set_hatch(h)
    ax.set_yticks(y)
    ax.set_yticklabels(labels)
    ax.invert_yaxis()
    ax.set_xlabel("Self-reported improvement on primary metric (%, higher = better)")
    ax.set_title("Outcome — how much each agent improved the lateral metric\n(grey + hatched = non-canonical platform / fabricated proxy)",
                 fontsize=11)
    ax.axvline(0, color="k", linewidth=0.5)
    ax.grid(True, axis="x", alpha=0.3)

    # annotate
    for i, (v, u, t) in enumerate(zip(vals, units, top)):
        txt = f"  {v:+.1f}% ({u}) — top: {t[:40]}"
        ax.text(v, i, txt, va="center", fontsize=8)

    # legend
    from matplotlib.patches import Patch
    legend_elems = [
        Patch(facecolor="#2a7ae2", edgecolor="black", label="canonical platform + measured truth"),
        Patch(facecolor="#888888", edgecolor="black", hatch="//", label="non-canonical (fabricated / wrong platform)"),
    ]
    ax.legend(handles=legend_elems, loc="lower right", fontsize=8)
    fig.tight_layout()
    return fig


def fig_attribution(cards: list[dict]) -> plt.Figure:
    """Per-agent stacked horizontal bar of variant contribution_pct.
    Each agent's variants are stacked using their own labels.
    """
    cards = sorted(cards, key=lambda c: c["agent_id"])
    fig, ax = plt.subplots(figsize=(9.5, 0.55 * len(cards) + 2.5))
    y = np.arange(len(cards))
    cmap = plt.get_cmap("tab20")

    for i, card in enumerate(cards):
        ab = card.get("attribution_breakdown", []) or []
        # Normalise positive/negative so negatives draw to the left of zero
        left_pos = 0.0
        left_neg = 0.0
        for j, v in enumerate(ab):
            pct = v.get("contribution_pct")
            if pct is None:
                continue
            color = cmap(j % 20)
            if pct >= 0:
                ax.barh(i, pct, left=left_pos, color=color, edgecolor="black", linewidth=0.4)
                if pct >= 4:  # only label visible chunks
                    ax.text(left_pos + pct / 2, i, f"{v.get('variant_name','?')[:24]}\n{pct:.1f}%",
                            ha="center", va="center", fontsize=7, color="black")
                left_pos += pct
            else:
                left_neg += pct
                ax.barh(i, pct, left=left_neg - pct, color=color, edgecolor="black", linewidth=0.4)
                ax.text(left_neg - pct / 2, i, f"{v.get('variant_name','?')[:18]}\n{pct:.1f}%",
                        ha="center", va="center", fontsize=7, color="black")

    ax.set_yticks(y)
    ax.set_yticklabels([c["agent_id"] for c in cards])
    ax.invert_yaxis()
    ax.set_xlabel("% of total improvement attributed to each variant (per the agent's own attribution scheme)")
    ax.set_title("Attribution breakdown — what each agent credits for the improvement",
                 fontsize=11)
    ax.axvline(0, color="k", linewidth=0.5)
    ax.set_xlim(-30, 110)
    ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout()
    return fig


def fig_rubric_heatmap(cards: list[dict]) -> plt.Figure:
    """Methodology rubric heatmap: agents × rubric items, green/red/grey."""
    cards = sorted(cards, key=lambda c: c["agent_id"])
    # Build a canonical list of item ids from the first card.
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
                grid[r, col] = -1  # null

    fig, ax = plt.subplots(figsize=(1.3 * len(item_ids) + 1.5, 0.45 * len(cards) + 2.0))
    cmap = matplotlib.colors.ListedColormap(["#cccccc", "#d9534f", "#5cb85c"])
    bounds = [-1.5, -0.5, 0.5, 1.5]
    norm = matplotlib.colors.BoundaryNorm(bounds, cmap.N)
    ax.imshow(grid, cmap=cmap, norm=norm, aspect="auto")

    # annotate cells
    for r in range(len(cards)):
        for col in range(len(item_ids)):
            val = grid[r, col]
            sym = {1: "✓", 0: "✗", -1: "—"}.get(int(val) if not np.isnan(val) else -2, "?")
            ax.text(col, r, sym, ha="center", va="center",
                    color="white", fontsize=11, fontweight="bold")

    ax.set_xticks(range(len(item_ids)))
    ax.set_xticklabels(item_ids, rotation=30, ha="right", fontsize=8)
    ax.set_yticks(range(len(cards)))
    ax.set_yticklabels([c["agent_id"] for c in cards], fontsize=9)
    ax.set_title("Methodology rubric — green ✓ pass, red ✗ fail, grey — null/not addressed",
                 fontsize=11)
    fig.tight_layout()
    return fig


def fig_summary_text(cards: list[dict]) -> plt.Figure:
    """Cover page with the cohort headline numbers as a styled text block."""
    n = len(cards)
    vals = [(c.get("headline", {}) or {}).get("improvement_pct_numeric") or 0.0 for c in cards]
    comparable_vals = [
        (c.get("headline", {}) or {}).get("improvement_pct_numeric") or 0.0
        for c in cards
        if (c.get("headline", {}) or {}).get("comparable_to_canonical") is True
    ]
    n_comparable = len(comparable_vals)
    n_noncomparable = n - n_comparable
    median_imp = float(np.median(vals)) if vals else 0.0
    range_imp = (min(vals), max(vals)) if vals else (0, 0)
    median_comp = float(np.median(comparable_vals)) if comparable_vals else 0.0

    fig, ax = plt.subplots(figsize=(8.5, 11))
    ax.axis("off")
    txt = [
        f"Cohort grading — {n} agents",
        "",
        f"Comparable-to-canonical:    {n_comparable}/{n}",
        f"Non-canonical / flagged:    {n_noncomparable}/{n}",
        "",
        f"Improvement on primary metric (self-reported, % — higher is better):",
        f"  • cohort median:                  {median_imp:+.1f}%",
        f"  • cohort range:                   {range_imp[0]:+.1f}% … {range_imp[1]:+.1f}%",
        f"  • median among canonical only:    {median_comp:+.1f}%",
        "",
        "Pages:",
        "  1 — Outcome bars (this view): per-agent % improvement, with non-canonical agents flagged",
        "  2 — Attribution: what each agent credits for the gain (stacked by their own variant labels)",
        "  3 — Rubric heatmap: methodology pass / fail / null per agent × rubric item",
        "",
        "Caveats:",
        "  • Improvement percentages are self-reported on the agent's chosen metric & unit.",
        "    Different agents picked rad/s, mrad/s, deg/s, and °/s on different masks and",
        "    splits. The % is the only universally-comparable axis; absolute values are not.",
        "  • A non-canonical bar (grey + hatched) means the agent scored on a non-canonical",
        "    platform OR substituted a fabricated proxy for the measured truth channel.",
        "    Its number is not directly comparable to the canonical bars.",
    ]
    ax.text(0.05, 0.95, "\n".join(txt), va="top", ha="left",
            family="monospace", fontsize=10)
    return fig


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--grade-dir", type=Path, required=True)
    args = p.parse_args()

    cards = load_cards(args.grade_dir)
    pdf_path = args.grade_dir / "cohort.pdf"

    with PdfPages(pdf_path) as pdf:
        pdf.savefig(fig_summary_text(cards))
        pdf.savefig(fig_outcome(cards))
        pdf.savefig(fig_attribution(cards))
        pdf.savefig(fig_rubric_heatmap(cards))

    print(f"cohort PDF: {pdf_path}")


if __name__ == "__main__":
    main()
