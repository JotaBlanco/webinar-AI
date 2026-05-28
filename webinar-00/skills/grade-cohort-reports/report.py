#!/usr/bin/env python3
"""Generate a PDF cohort report from grade-cohort-reports outputs.

Reads:
    <grade-dir>/raw/<agent_id>.json       # per-agent strict-JSON scorecards
    <grade-dir>/canonical/<agent_id>.json # optional canonical-eval scorecards
    <grade-dir>/families.json             # optional {agent_id: family_label}

Writes:
    <grade-dir>/cohort.pdf

Pages auto-scale to cohort size. Per-agent rows use a fixed row-height in
inches (so 5 agents and 85 agents both render at a legible row spacing) and
the figure grows as needed.
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


PAGE_PORTRAIT = (8.5, 11.0)
ROW_HEIGHT_IN = 0.22         # inches per agent row — large enough for readable tick labels
MIN_FIG_HEIGHT = 6.0
MAX_FIG_HEIGHT = 36.0        # cap for very large cohorts; PDFs are scrollable anyway
TOP_BOTTOM_PAD_IN = 2.5      # space reserved for title + xlabel + legend


def _fig_size_for_n(n: int, width: float = 14.0) -> tuple[float, float]:
    """Figure size that grows with row count but stays inside a sane envelope.

    The width is wide-landscape (14 in) so bars get room; the height grows linearly
    with N up to MAX_FIG_HEIGHT and then stops (rows shrink instead)."""
    h = min(MAX_FIG_HEIGHT, max(MIN_FIG_HEIGHT, n * ROW_HEIGHT_IN + TOP_BOTTOM_PAD_IN))
    return (width, h)


def _tick_fontsize(n: int) -> float:
    """Tick-label font size that scales down for big cohorts but never <6pt."""
    if n <= 20:
        return 10
    if n <= 40:
        return 8
    if n <= 60:
        return 7
    return 6


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
    cards.sort(key=lambda c: c["agent_id"])
    return cards


def load_canonical_and_families(grade_dir: Path) -> tuple[list[dict], dict[str, str]]:
    """Return (canonical_cards, families). Empty list/dict if not present."""
    canon_dir = grade_dir / "canonical"
    canonical: list[dict] = []
    if canon_dir.is_dir():
        for f in sorted(canon_dir.glob("*.json")):
            if f.name in ("baseline.json", "agent-folders.json"):
                continue
            try:
                canonical.append(json.loads(f.read_text()))
            except json.JSONDecodeError:
                pass
    families: dict[str, str] = {}
    fams_file = grade_dir / "families.json"
    if fams_file.is_file():
        try:
            families = json.loads(fams_file.read_text())
        except json.JSONDecodeError:
            pass
    return canonical, families


# ---------------------------------------------------------------------------
# Page 1 — cover
# ---------------------------------------------------------------------------

def fig_summary(cards: list[dict], families: dict[str, str]) -> plt.Figure:
    n = len(cards)
    vals = [(c.get("headline", {}) or {}).get("improvement_pct_numeric") or 0.0 for c in cards]
    canonical_only = [
        (c.get("headline", {}) or {}).get("improvement_pct_numeric") or 0.0
        for c in cards
        if (c.get("headline", {}) or {}).get("comparable_to_canonical") is True
    ]
    n_canonical = len(canonical_only)
    n_flagged = n - n_canonical
    median_all = float(np.median(vals)) if vals else 0.0
    median_canon = float(np.median(canonical_only)) if canonical_only else 0.0
    lo, hi = (min(vals), max(vals)) if vals else (0, 0)

    fam_counts: dict[str, int] = {}
    for c in cards:
        fam = families.get(c["agent_id"], "unknown")
        fam_counts[fam] = fam_counts.get(fam, 0) + 1
    fam_order = sorted(fam_counts.keys(), key=lambda f: (f != "raw", f))

    fig = plt.figure(figsize=PAGE_PORTRAIT)
    fig.subplots_adjust(left=0.08, right=0.92, top=0.94, bottom=0.06)
    ax = fig.add_subplot(111)
    ax.axis("off")

    ax.text(0.0, 1.00, "Cohort grading report", transform=ax.transAxes,
            fontsize=22, fontweight="bold", va="top")
    ax.text(0.0, 0.955, f"{n} agents · {len(fam_counts)} families · alphabetical order throughout",
            transform=ax.transAxes, fontsize=10.5, color="#555", va="top")

    rows = [
        ("Canonical platform / measured truth", f"{n_canonical} / {n}"),
        ("Non-canonical / flagged",              f"{n_flagged} / {n}"),
        ("",                                     ""),
        ("Median improvement (all)",             f"{median_all:+.1f} %"),
        ("Median improvement (canonical only)",  f"{median_canon:+.1f} %"),
        ("Range across cohort",                  f"{lo:+.1f} %  …  {hi:+.1f} %"),
    ]
    y = 0.87
    for k, v in rows:
        ax.text(0.0,  y, k, transform=ax.transAxes, fontsize=10.5, va="top")
        ax.text(0.55, y, v, transform=ax.transAxes, fontsize=10.5, va="top", family="monospace")
        y -= 0.034

    # Families — two-column layout so up to ~30 fit cleanly above the contents block.
    ax.text(0.0, 0.60, "Families in this cohort", transform=ax.transAxes,
            fontsize=13, fontweight="bold", va="top")
    n_fams = len(fam_order)
    col_a_n = (n_fams + 1) // 2
    cols = [
        (0.02, 0.27, fam_order[:col_a_n]),
        (0.52, 0.77, fam_order[col_a_n:]),
    ]
    for x_label, x_value, items in cols:
        y = 0.555
        for fam in items:
            ax.text(x_label, y, fam, transform=ax.transAxes, fontsize=9, va="top")
            ax.text(x_value, y, f"n = {fam_counts[fam]}", transform=ax.transAxes,
                    fontsize=9, va="top", family="monospace")
            y -= 0.022

    # Contents
    ax.text(0.0, 0.28, "Contents", transform=ax.transAxes,
            fontsize=13, fontweight="bold", va="top")
    pages = [
        "Page 2 — Outcome bars: per-agent self-reported % improvement",
        "Page 3 — Attribution: variant contributions per agent",
        "Page 4 — Methodology rubric heatmap (agents × rubric items)",
        "Page 5 — Canonical re-evaluation by family (if canonical data available)",
    ]
    y = 0.235
    for line in pages:
        ax.text(0.02, y, line, transform=ax.transAxes, fontsize=10, va="top")
        y -= 0.028

    # Caveats
    ax.text(0.0, 0.105, "Caveats", transform=ax.transAxes,
            fontsize=12, fontweight="bold", va="top")
    cavs = [
        "Self-reported % uses each agent's chosen metric, unit, and split — not comparable across agents.",
        "Canonical % (page 5) re-runs every model on the same fixed eval set — this IS comparable.",
        "Grey bars on page 2 = agent scored on non-canonical platform or fabricated proxy.",
    ]
    y = 0.075
    for line in cavs:
        ax.text(0.02, y, line, transform=ax.transAxes, fontsize=8.5, va="top", color="#333")
        y -= 0.022
    return fig


# ---------------------------------------------------------------------------
# Page 2 — outcome (self-reported)
# ---------------------------------------------------------------------------

def fig_outcome(cards: list[dict]) -> plt.Figure:
    n = len(cards)
    labels = [c["agent_id"] for c in cards]
    vals = [(c.get("headline", {}) or {}).get("improvement_pct_numeric") or 0.0 for c in cards]
    units = [(c.get("headline", {}) or {}).get("unit_normalized") or "?" for c in cards]
    canonical = [(c.get("headline", {}) or {}).get("comparable_to_canonical") for c in cards]

    fig = plt.figure(figsize=_fig_size_for_n(n))
    fig.subplots_adjust(left=0.22, right=0.93, top=0.94, bottom=0.06)
    ax = fig.add_subplot(111)

    y = np.arange(n)
    colours = ["#2a7ae2" if c else "#9a9a9a" for c in canonical]
    ax.barh(y, vals, color=colours, edgecolor="black", linewidth=0.4, height=0.78)

    tick_fs = _tick_fontsize(n)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=tick_fs)
    ax.invert_yaxis()
    ax.set_xlabel("Self-reported improvement on primary metric (%)", fontsize=10)
    ax.set_title("Self-reported outcome — improvement on the lateral metric (alphabetical)",
                 fontsize=12, pad=12)
    ax.axvline(0, color="k", linewidth=0.5)
    ax.grid(True, axis="x", alpha=0.3)

    lo_val = min(vals + [0])
    hi_val = max(vals + [0])
    pad = max(5.0, (hi_val - lo_val) * 0.08)
    ax.set_xlim(lo_val - pad, hi_val + pad * 2.5)

    label_fs = max(5.5, tick_fs - 1)
    for i, (v, u) in enumerate(zip(vals, units)):
        ha = "left" if v >= 0 else "right"
        x_off = (hi_val - lo_val) * 0.01 * (1 if v >= 0 else -1)
        ax.text(v + x_off, i, f"{v:+.1f}%  ({u})",
                va="center", ha=ha, fontsize=label_fs, color="black")

    ax.legend(handles=[
        Patch(facecolor="#2a7ae2", edgecolor="black", label="canonical platform"),
        Patch(facecolor="#9a9a9a", edgecolor="black", label="non-canonical / flagged"),
    ], loc="lower right", fontsize=9, framealpha=0.95)
    return fig


# ---------------------------------------------------------------------------
# Page 3 — attribution stacked bars
# ---------------------------------------------------------------------------

def fig_attribution(cards: list[dict]) -> plt.Figure:
    n = len(cards)
    fig = plt.figure(figsize=_fig_size_for_n(n))
    fig.subplots_adjust(left=0.22, right=0.93, top=0.94, bottom=0.06)
    ax = fig.add_subplot(111)
    y = np.arange(n)
    cmap = plt.get_cmap("tab20")
    tick_fs = _tick_fontsize(n)
    # Label only chunks visibly wide enough — threshold scales with N (fewer labels for big cohorts).
    label_min_width = 12.0 if n > 40 else 8.0
    label_fs = max(5.5, tick_fs - 2)

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
            short = (name[:18] + "…") if len(name) > 19 else name
            if pct >= 0:
                ax.barh(i, pct, left=left_pos, color=color,
                        edgecolor="black", linewidth=0.3, height=0.78)
                if pct >= label_min_width:
                    ax.text(left_pos + pct / 2, i, f"{short} {pct:.0f}%",
                            ha="center", va="center", fontsize=label_fs, color="black",
                            clip_on=True)
                left_pos += pct
            else:
                left_neg += pct
                ax.barh(i, pct, left=left_neg - pct, color=color,
                        edgecolor="black", linewidth=0.3, height=0.78)
                if abs(pct) >= label_min_width:
                    ax.text(left_neg - pct / 2, i, f"{short} {pct:.0f}%",
                            ha="center", va="center", fontsize=label_fs, color="black",
                            clip_on=True)

    ax.set_yticks(y)
    ax.set_yticklabels([c["agent_id"] for c in cards], fontsize=tick_fs)
    ax.invert_yaxis()
    ax.set_xlabel("% of total improvement attributed to each variant (agent's own scheme)", fontsize=10)
    ax.set_title("Attribution — variant contributions per agent (alphabetical)",
                 fontsize=12, pad=12)
    ax.axvline(0, color="k", linewidth=0.5)
    ax.set_xlim(-30, 110)
    ax.grid(True, axis="x", alpha=0.3)
    return fig


# ---------------------------------------------------------------------------
# Page 4 — rubric heatmap
# ---------------------------------------------------------------------------

def fig_rubric_heatmap(cards: list[dict]) -> plt.Figure:
    item_ids = []
    for c in cards:
        for it in c.get("items", []):
            if it["id"] not in item_ids:
                item_ids.append(it["id"])

    n = len(cards)
    grid = np.full((n, len(item_ids)), np.nan)
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

    fig = plt.figure(figsize=_fig_size_for_n(n))
    fig.subplots_adjust(left=0.22, right=0.96, top=0.94, bottom=0.10)
    ax = fig.add_subplot(111)

    cmap = matplotlib.colors.ListedColormap(["#cccccc", "#d9534f", "#5cb85c"])
    bounds = [-1.5, -0.5, 0.5, 1.5]
    norm = matplotlib.colors.BoundaryNorm(bounds, cmap.N)

    nr, nc = grid.shape
    X = np.arange(nc + 1)
    Y = np.arange(nr + 1)
    ax.pcolormesh(X, Y, grid, cmap=cmap, norm=norm, edgecolors="white", linewidth=1.0)

    tick_fs = _tick_fontsize(n)
    sym_fs = max(7, min(14, int(280 / max(nr, 10))))
    for r in range(nr):
        for col in range(nc):
            v = grid[r, col]
            sym = {1: "✓", 0: "✗", -1: "—"}.get(int(v) if not np.isnan(v) else -99, "?")
            ax.text(col + 0.5, r + 0.5, sym, ha="center", va="center",
                    color="white", fontsize=sym_fs, fontweight="bold")

    ax.set_xticks(np.arange(nc) + 0.5)
    ax.set_xticklabels(item_ids, rotation=25, ha="right", fontsize=9)
    ax.set_yticks(np.arange(nr) + 0.5)
    ax.set_yticklabels([c["agent_id"] for c in cards], fontsize=tick_fs)
    ax.invert_yaxis()
    ax.set_xlim(0, nc)
    ax.set_ylim(nr, 0)
    ax.set_title("Methodology rubric — green ✓ pass · red ✗ fail · grey — null / not addressed",
                 fontsize=12, pad=12)
    ax.tick_params(length=0)
    return fig


# ---------------------------------------------------------------------------
# Page 5 — canonical evaluation by family
# ---------------------------------------------------------------------------

def fig_canonical_by_family(canonical: list[dict], families: dict[str, str]) -> plt.Figure | None:
    if not canonical or not families:
        return None

    rows = []
    for c in canonical:
        aid = c.get("agent_id", "?")
        fam = families.get(aid, "unknown")
        if c.get("status") == "ok" and c.get("improvement_pct") is not None:
            rows.append((fam, aid, float(c["improvement_pct"])))
        else:
            rows.append((fam, aid, None))

    fam_order = sorted({r[0] for r in rows}, key=lambda f: (f != "raw", f))
    rows.sort(key=lambda r: (fam_order.index(r[0]), r[1]))

    n = len(rows)
    fig = plt.figure(figsize=_fig_size_for_n(n))
    fig.subplots_adjust(left=0.22, right=0.93, top=0.94, bottom=0.06)
    ax = fig.add_subplot(111)

    y = np.arange(n)
    vals = [(r[2] if r[2] is not None else 0.0) for r in rows]
    cmap = plt.get_cmap("tab10")
    fam_colour = {f: cmap(i % 10) for i, f in enumerate(fam_order)}
    colours = [fam_colour[r[0]] for r in rows]
    ax.barh(y, vals, color=colours, edgecolor="black", linewidth=0.3, height=0.78)

    tick_fs = _tick_fontsize(n)
    ax.set_yticks(y)
    ax.set_yticklabels([r[1] for r in rows], fontsize=tick_fs)
    ax.invert_yaxis()
    ax.axvline(0, color="k", linewidth=0.6)
    ax.set_xlabel("Canonical Δ% vs V0 (positive = better)", fontsize=10)
    ax.set_title("Canonical evaluation by family — every model re-run on fixed Ford eval set",
                 fontsize=12, pad=12)
    ax.grid(True, axis="x", alpha=0.3)

    fam_means: dict[str, float | None] = {}
    cur_fam = rows[0][0]
    fam_start = 0
    for i in range(n + 1):
        nxt_fam = rows[i][0] if i < n else None
        if nxt_fam != cur_fam:
            block = [r[2] for r in rows[fam_start:i] if r[2] is not None]
            fam_means[cur_fam] = (sum(block) / len(block)) if block else None
            if i < n:
                ax.axhline(i - 0.5, color="#555", linewidth=0.6, linestyle="--")
            cur_fam = nxt_fam
            fam_start = i

    lo_val = min(vals + [0])
    hi_val = max(vals + [0])
    pad = max(5.0, (hi_val - lo_val) * 0.08)
    ax.set_xlim(lo_val - pad, hi_val + pad * 2.5)

    label_fs = max(5.5, tick_fs - 1)
    for i, v in enumerate(vals):
        ha = "left" if v >= 0 else "right"
        x_off = (hi_val - lo_val) * 0.01 * (1 if v >= 0 else -1)
        ax.text(v + x_off, i, f"{v:+.1f}%",
                va="center", ha=ha, fontsize=label_fs, color="black")

    legend_handles = []
    for f in fam_order:
        mean_val = fam_means.get(f)
        label = f"{f}  (mean Δ% = {mean_val:+.1f})" if mean_val is not None else f
        legend_handles.append(Patch(facecolor=fam_colour[f], edgecolor="black", label=label))
    ax.legend(handles=legend_handles, loc="lower right", fontsize=8, framealpha=0.95,
              title="Family (mean canonical Δ%)", title_fontsize=8)
    return fig


# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--grade-dir", type=Path, required=True)
    args = p.parse_args()

    cards = load_cards(args.grade_dir)
    canonical, families = load_canonical_and_families(args.grade_dir)
    pdf_path = args.grade_dir / "cohort.pdf"

    with PdfPages(pdf_path) as pdf:
        # Cover: tight bbox is fine — it's a small portrait page.
        pdf.savefig(fig_summary(cards, families), bbox_inches="tight")
        # Per-agent pages: DO NOT use bbox_inches="tight" — it expands the
        # figure to accommodate any text overflow, which produced a 14000-pixel
        # wide attribution page in earlier versions. We've already sized the
        # figure correctly via _fig_size_for_n; save at that exact size.
        pdf.savefig(fig_outcome(cards))
        pdf.savefig(fig_attribution(cards))
        pdf.savefig(fig_rubric_heatmap(cards))
        fig_canon = fig_canonical_by_family(canonical, families)
        if fig_canon is not None:
            pdf.savefig(fig_canon)

    print(f"cohort PDF: {pdf_path}")


if __name__ == "__main__":
    main()
