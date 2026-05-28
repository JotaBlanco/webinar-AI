#!/usr/bin/env python3
"""Render the cohort report as a self-contained HTML file styled with Quix branding.

Uses the quix-toolkit-for-ai `quix-report-styling` skill: reads
template-light.html (or template-dark.html), extracts the `<style>` block
and the hero / footer logo SVGs, and builds the body programmatically with
the Quix CSS class names (key-finding, card card-blue, metric metric-good,
figure, critical, conclusion, etc.).

The matplotlib figures are reused from report.py and embedded as base64
PNGs so the HTML stays single-file with no external dependencies — same
rule the styling skill enforces on its templates.

Reads:
    <grade-dir>/raw/<agent_id>.json
    <grade-dir>/canonical/<agent_id>.json   (optional)
    <grade-dir>/families.json               (optional)

Writes:
    <grade-dir>/cohort.html
"""

import argparse
import base64
import html
import io
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Reuse the figure functions and loaders from report.py.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import report as pdf_report  # noqa: E402


QUIX_SKILL_DIR = Path(
    "/Users/javiquix/Desktop/quixio/quix-toolkit-for-ai/skills/quix-report-styling"
)


# ---------------------------------------------------------------------------
# Template scraping — pull <style>, hero SVG, footer SVG from the Quix file.
# ---------------------------------------------------------------------------

def _read_template_assets(theme: str) -> tuple[str, str, str]:
    """Return (style_block, hero_logo_svg, footer_logo_svg)."""
    path = QUIX_SKILL_DIR / f"template-{theme}.html"
    if not path.is_file():
        sys.exit(f"report_html: Quix template not found: {path}")
    txt = path.read_text()
    style = _extract(r"<style>.*?</style>", txt, "style block")
    hero_svg = _extract(r'<svg class="hero-logo".*?</svg>', txt, "hero logo SVG")
    footer_match = re.search(r"<footer class=\"footer\">(.*?)</footer>", txt, re.DOTALL)
    footer_inner = footer_match.group(1) if footer_match else ""
    # Strip the {{FOOTER_TEXT}} placeholder — we'll replace it ourselves.
    footer_inner = footer_inner.replace("{{FOOTER_TEXT}}", "").strip()
    return style, hero_svg, footer_inner


def _extract(pattern: str, txt: str, label: str) -> str:
    m = re.search(pattern, txt, re.DOTALL)
    if not m:
        sys.exit(f"report_html: could not extract {label} from Quix template")
    return m.group(0)


# ---------------------------------------------------------------------------
# Figure → base64 PNG (single-file rule).
# ---------------------------------------------------------------------------

def _fig_to_data_uri(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=140, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


# ---------------------------------------------------------------------------
# Section builders.
# ---------------------------------------------------------------------------

def _cohort_stats(cards: list[dict]) -> dict:
    vals = [(c.get("headline", {}) or {}).get("improvement_pct_numeric") or 0.0 for c in cards]
    canonical_only = [
        (c.get("headline", {}) or {}).get("improvement_pct_numeric") or 0.0
        for c in cards
        if (c.get("headline", {}) or {}).get("comparable_to_canonical") is True
    ]
    n = len(cards)
    return {
        "n": n,
        "n_canonical": len(canonical_only),
        "n_flagged": n - len(canonical_only),
        "median_all": float(np.median(vals)) if vals else 0.0,
        "median_canon": float(np.median(canonical_only)) if canonical_only else 0.0,
        "lo": min(vals) if vals else 0.0,
        "hi": max(vals) if vals else 0.0,
    }


def _per_item_pass_rate(cards: list[dict]) -> list[tuple[str, int, int, int]]:
    """Return [(item_id, n_pass, n_fail, n_null)] preserving rubric order."""
    ids: list[str] = []
    seen: set[str] = set()
    for c in cards:
        for it in c.get("items", []):
            rid = it.get("id")
            if rid and rid not in seen:
                seen.add(rid)
                ids.append(rid)
    rows = []
    for rid in ids:
        npass = nfail = nnull = 0
        for c in cards:
            for it in c.get("items", []):
                if it.get("id") != rid:
                    continue
                r = it.get("result")
                if r is True:
                    npass += 1
                elif r is False:
                    nfail += 1
                else:
                    nnull += 1
        rows.append((rid, npass, nfail, nnull))
    return rows


def _hero(idea_id: str, stats: dict, families: dict, hero_svg: str) -> str:
    subtitle = (
        f"{stats['n']} agents · {len(set(families.values())) or 1} family"
        f"{'ies' if (len(set(families.values())) or 1) != 1 else ''} · "
        f"rubric: {html.escape(idea_id)}"
    )
    title = f"Cohort grading — {html.escape(idea_id)}"
    return f"""
<header class="hero">
  <div class="container">
    {hero_svg}
    <h1>{title}</h1>
    <p class="subtitle">{subtitle}</p>
  </div>
</header>
"""


def _executive_summary(stats: dict) -> str:
    n_canon = stats["n_canonical"]
    n = stats["n"]
    med_canon = stats["median_canon"]
    med_all = stats["median_all"]
    lo, hi = stats["lo"], stats["hi"]
    metric_class = "metric-good" if med_canon > 0 else "metric-warn"
    return f"""
<section class="section">
  <div class="container">
    <h2 class="accent-blue">Executive Summary</h2>

    <div class="key-finding">
      <p>
        <strong>{n_canon} of {n} agents</strong> scored on the canonical platform with a measured truth channel.
        Median self-reported improvement among canonical agents:
        <span class="metric {metric_class}">{med_canon:+.1f}%</span>
        Spread across the full cohort:
        <span class="metric">{lo:+.1f}% … {hi:+.1f}%</span>
      </p>
    </div>

    <div class="card card-blue">
      <ul>
        <li><strong>Cohort size:</strong> {n} agents · <span class="metric">{n_canon} canonical · {stats['n_flagged']} flagged</span></li>
        <li><strong>Median improvement (all agents):</strong> <span class="metric">{med_all:+.1f}%</span> — self-reported, on each agent's chosen metric.</li>
        <li><strong>Median improvement (canonical only):</strong> <span class="metric metric-good">{med_canon:+.1f}%</span> — restricted to agents on the rubric-canonical setup.</li>
        <li><strong>Comparability caveat:</strong> Self-reported numbers use different metrics, units, and splits per agent. The percentage is the only universally comparable axis.</li>
      </ul>
    </div>
  </div>
</section>
"""


def _section_figure(*, n: int, accent: str, title: str, body: str,
                    fig_data_uri: str, caption: str, takeaway: str | None,
                    alt_bg: bool = False, card_class: str | None = None,
                    callout: str = "key-finding") -> str:
    """One figure section — accent rotates blue → purple → orange across sections."""
    cls = card_class or f"card card-{accent}"
    section_class = "section section-alt" if alt_bg else "section"
    takeaway_block = ""
    if takeaway:
        takeaway_block = f"""
      <div class="{callout}">
        <p>{takeaway}</p>
      </div>
"""
    return f"""
<section class="{section_class}">
  <div class="container">
    <h2 class="accent-{accent}">{n}. {html.escape(title)}</h2>

    <div class="{cls}">
      <p>{body}</p>

      <div class="figure">
        <img src="{fig_data_uri}" alt="{html.escape(title)}">
        <p class="figure-caption">Figure {n}: {caption}</p>
      </div>
{takeaway_block}    </div>
  </div>
</section>
"""


def _rubric_table(rows: list[tuple[str, int, int, int]], n: int) -> str:
    body = []
    for rid, npass, nfail, nnull in rows:
        denom = npass + nfail
        rate_pct = (npass / denom * 100) if denom else 0.0
        # Cell class:
        if denom == 0:
            cell_cls = ""
            rate_str = "—"
        elif rate_pct >= 80:
            cell_cls = " class=\"val-good\""
            rate_str = f"{rate_pct:.0f}%"
        elif rate_pct <= 20:
            cell_cls = " class=\"val-bad\""
            rate_str = f"{rate_pct:.0f}%"
        else:
            cell_cls = ""
            rate_str = f"{rate_pct:.0f}%"
        body.append(
            f"<tr><td><code>{html.escape(rid)}</code></td>"
            f"<td>{npass}</td><td>{nfail}</td><td>{nnull}</td>"
            f"<td{cell_cls}>{rate_str}</td></tr>"
        )
    return f"""
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Rubric item</th>
              <th>Pass</th>
              <th>Fail</th>
              <th>Null</th>
              <th>Pass rate (excl. null)</th>
            </tr>
          </thead>
          <tbody>
            {"".join(body)}
          </tbody>
        </table>
      </div>
"""


def _conclusions(rows: list[tuple[str, int, int, int]], stats: dict) -> str:
    # Worst items by fail count.
    sorted_rows = sorted(rows, key=lambda r: (-r[2], -r[1]))
    worst = [r for r in sorted_rows if r[2] > 0][:3]

    if worst:
        findings = []
        for rid, npass, nfail, nnull in worst:
            findings.append(
                f"<li><strong><code>{html.escape(rid)}</code> — failed by {nfail}/{stats['n']} agents.</strong> "
                f"This is a substrate gap: the naked prompt does not surface this item, so adding it "
                f"to the next module's AGENTS.md / skills will likely move the needle.</li>"
            )
        findings_html = "\n              ".join(findings)
    else:
        findings_html = "<li>No rubric items failed — every dimension was addressed by the cohort.</li>"

    main = (
        f"The cohort hit a median self-reported improvement of "
        f"<span class=\"metric {'metric-good' if stats['median_canon'] > 0 else 'metric-warn'}\">"
        f"{stats['median_canon']:+.1f}%</span> on canonical agents, with the rubric exposing "
        f"{len(worst)} item{'s' if len(worst) != 1 else ''} that the cohort consistently missed."
    )
    caveat = (
        "Self-reported improvement uses each agent's chosen metric and split — not "
        "directly comparable across agents. A canonical re-evaluation (page 4 figure) is "
        "the only apples-to-apples view."
    )
    return f"""
<section class="section section-alt">
  <div class="container">
    <h2 class="accent-orange">Conclusions</h2>

    <div class="conclusion">
      <p>{main}</p>
    </div>

    <div class="card card-orange">
      <h3>Trap-trip hotspots — items the cohort missed</h3>
      <ol>
              {findings_html}
      </ol>
    </div>

    <div class="critical">
      <p><strong>Caveat:</strong> {caveat}</p>
    </div>
  </div>
</section>
"""


def _future_work() -> str:
    return """
<section class="section">
  <div class="container">
    <h2 class="accent-blue">Future Work</h2>

    <div class="grid-2">
      <div class="card card-blue">
        <h3>Immediate next steps</h3>
        <ol>
          <li><strong>Promote the top trap-trip hotspot into the next module's substrate</strong> — add one line to AGENTS.md or a skill that cures the failing rubric item, then re-grade to see whether the pass rate moves.</li>
          <li><strong>Run a canonical re-evaluation if not yet present</strong> — re-score every agent's model on a fixed Ford eval set so improvement numbers become directly comparable.</li>
        </ol>
      </div>
      <div class="card card-purple">
        <h3>Workshop-level moves</h3>
        <ol>
          <li><strong>Expand the rubric where the judge could not score</strong> — a high null count on a rubric item means the rubric criterion is too narrow; sharpen it.</li>
          <li><strong>Cross-idea cohorts</strong> — run the same grading pipeline on `idea-02`, `idea-03`, etc. and compare which substrate gaps reappear across ideas.</li>
        </ol>
      </div>
    </div>
  </div>
</section>
"""


def _footer(footer_inner: str) -> str:
    text = "Generated by <code>grade-cohort-reports</code> · styled with the Quix design system"
    return f"""
<footer class="footer">
  {footer_inner}
  <br>
  {text}
</footer>
"""


# ---------------------------------------------------------------------------
# Build.
# ---------------------------------------------------------------------------

def build_html(grade_dir: Path, theme: str = "light", idea_id: str = "") -> str:
    cards = pdf_report.load_cards(grade_dir)
    canonical, families = pdf_report.load_canonical_and_families(grade_dir)
    stats = _cohort_stats(cards)
    rubric_rows = _per_item_pass_rate(cards)

    style, hero_svg, footer_inner = _read_template_assets(theme)

    # Figures (reuse pdf_report functions — single source of truth).
    outcome_uri    = _fig_to_data_uri(pdf_report.fig_outcome(cards))
    attribution_uri = _fig_to_data_uri(pdf_report.fig_attribution(cards))
    rubric_uri     = _fig_to_data_uri(pdf_report.fig_rubric_heatmap(cards))
    canon_fig = pdf_report.fig_canonical_by_family(canonical, families) if canonical and families else None
    canon_uri = _fig_to_data_uri(canon_fig) if canon_fig is not None else None

    # Compose body. Accents rotate blue → purple → orange → blue → ... across data sections.
    accents = ["purple", "orange", "blue"]
    sections: list[str] = []

    sections.append(_hero(idea_id or "(no idea-id set)", stats, families, hero_svg))
    sections.append(_executive_summary(stats))

    sections.append(_section_figure(
        n=1, accent=accents[0],
        title="Self-reported improvement on the primary metric",
        body=(
            "Each bar is one agent's self-reported improvement, sorted alphabetically. "
            "Bars in grey are agents that scored on a non-canonical platform or substituted a "
            "fabricated proxy for the measured truth channel — their numbers are not directly "
            "comparable to the canonical bars."
        ),
        fig_data_uri=outcome_uri,
        caption=(
            f"Self-reported % improvement across {stats['n']} agents. "
            f"Median (canonical only): {stats['median_canon']:+.1f}%. "
            f"Outlier bars are flagged because the underlying metric, mask, or platform "
            f"differs from what the rubric considers canonical."
        ),
        takeaway=(
            "Self-reported numbers establish that the cohort can improve the metric, "
            "but the spread is dominated by metric choice, not modelling skill."
        ),
        alt_bg=True,
    ))

    sections.append(_section_figure(
        n=2, accent=accents[1],
        title="Attribution — what each agent credits for the gain",
        body=(
            "Per-agent stacked bars showing the % of total improvement each variant on the "
            "agent's ladder contributes. Variant names are the agent's own labels — no "
            "normalisation across the cohort, because the cohort spread itself is part of "
            "the workshop signal."
        ),
        fig_data_uri=attribution_uri,
        caption=(
            "Attribution breakdown by variant per agent. Look for chunks that recur across "
            "agents under different names — that recurring concept is the load-bearing fix; "
            "everything else is polish."
        ),
        takeaway=None,
    ))

    sections.append(_section_figure(
        n=3, accent=accents[2],
        title="Methodology rubric — pass / fail per agent",
        body=(
            "Each cell is one rubric item for one agent: green ✓ pass, red ✗ fail, grey — null "
            "(item not addressed in the report). Vertical stripes of red are the substrate gaps: "
            "items that no agent covered without explicit prompting."
        ),
        fig_data_uri=rubric_uri,
        caption=(
            "Methodology rubric across the cohort. A solid-red column is a substrate gap; "
            "the corresponding rubric item is exactly what the next module's AGENTS.md or "
            "skill should add."
        ),
        takeaway=None,
        alt_bg=True,
    ))

    # Per-item pass-rate table — same data, machine-readable.
    # Accent rotation continues: blue→purple→orange→blue→purple→…
    table_html = _rubric_table(rubric_rows, stats["n"])
    sections.append(f"""
<section class="section">
  <div class="container">
    <h2 class="accent-purple">4. Rubric pass-rate table</h2>
    <div class="card card-purple">
      <p>The numbers behind the heatmap. Pass rate excludes null rows.</p>
      {table_html}
    </div>
  </div>
</section>
""")

    if canon_uri is not None:
        sections.append(_section_figure(
            n=5, accent="orange",
            title="Canonical re-evaluation by family",
            body=(
                "Every agent's model re-run on the same fixed evaluation set. This is the only "
                "view that compares numbers like-for-like across the cohort, because the metric, "
                "platform, and split are now identical."
            ),
            fig_data_uri=canon_uri,
            caption=(
                "Canonical Δ% per agent, grouped by family. Dashed lines separate families; the "
                "legend shows each family's mean Δ%."
            ),
            takeaway=None,
            alt_bg=True,
        ))

    sections.append(_conclusions(rubric_rows, stats))
    sections.append(_future_work())
    sections.append(_footer(footer_inner))

    body = "\n".join(sections)
    page_title = f"Cohort grading — {html.escape(idea_id)}" if idea_id else "Cohort grading"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{page_title}</title>
{style}
</head>
<body>
{body}
</body>
</html>
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--grade-dir", type=Path, required=True)
    p.add_argument("--theme", choices=["light", "dark"], default="light",
                   help="Quix template theme to use (default: light)")
    p.add_argument("--idea-id", default="",
                   help="optional idea-id string for the hero title")
    args = p.parse_args()

    html_text = build_html(args.grade_dir, theme=args.theme, idea_id=args.idea_id)
    out_path = args.grade_dir / "cohort.html"
    out_path.write_text(html_text)
    print(f"cohort HTML: {out_path}")


if __name__ == "__main__":
    main()
