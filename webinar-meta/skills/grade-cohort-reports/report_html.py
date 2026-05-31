"""Render cohort.html from cohort.json.

Two HTML outputs are produced from the same render:
  - cohort.html         (interactive — plotly widgets, plotly.js from CDN)
  - cohort.print.html   (static — plotly figures rendered as inline SVG, no JS)

The print version is what report_pdf.py feeds to weasyprint.

Both inherit the CSS class system from the quix-report-styling skill (light theme)
so the visual language is consistent with other Quix reports.
"""

from __future__ import annotations

import argparse
import datetime
import html
import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
STYLING_SKILL_LIGHT = Path("/Users/javiquix/Desktop/quixio/quix-toolkit-for-ai/skills/quix-report-styling/template-light.html")

sys.path.insert(0, str(SKILL_DIR))
import chart  # noqa: E402


def extract_style_and_logo(template_path: Path) -> tuple[str, str]:
    """Pull (<style>...</style>, hero SVG logo) from the light template — our single
    source of truth for visual language."""
    text = template_path.read_text()
    m_style = re.search(r"<style>(.*?)</style>", text, re.DOTALL)
    if not m_style:
        sys.exit(f"report_html: no <style> block in {template_path}")
    style_block = m_style.group(0)

    # Pull the hero logo SVG (first svg in the file).
    m_logo = re.search(r'(<svg class="hero-logo".*?</svg>)', text, re.DOTALL)
    logo = m_logo.group(1) if m_logo else ""
    return style_block, logo


def fmt_pct(v) -> str:
    if v is None:
        return "—"
    return f"{v:+.1f}%"


def fmt_n(v, digits=4) -> str:
    if v is None:
        return "—"
    return f"{v:.{digits}f}"


def metric_class(v) -> str:
    """For numeric improvement: green ≥ +20, neutral 0–20, red ≤ 0."""
    if v is None:
        return ""
    if v >= 20:
        return "metric-good"
    if v <= 0:
        return "metric-bad"
    return ""


def callout_headline(cohort: dict) -> str:
    w = cohort["winners"]
    parts = []
    if w["yaw_top3"]:
        a, v = w["yaw_top3"][0]
        parts.append(f'Best yaw: <code>{a}</code> <span class="metric metric-good">{fmt_pct(v)}</span>')
    if w["cte_top3"]:
        a, v = w["cte_top3"][0]
        parts.append(f'Best CTE: <code>{a}</code> <span class="metric metric-good">{fmt_pct(v)}</span>')
    band = w["double_30"] or w["double_25"]
    threshold = 30 if w["double_30"] else 25
    band_str = ""
    if band:
        ids = ", ".join(f"<code>{html.escape(a)}</code>" for a in band)
        band_str = f'<br><strong>Winning both KPIs ≥ +{threshold}%</strong> ({len(band)} agents): {ids}'
    return " · ".join(parts) + band_str


def family_table(cohort: dict) -> str:
    out = [
        "<div class='table-wrap'><table><thead><tr>",
        "<th>family</th><th>n ok / total</th><th>yaw Δ% (mean ± σ)</th><th>CTE Δ% (mean ± σ)</th><th>failures</th>",
        "</tr></thead><tbody>",
    ]
    for fam in cohort["family_order"]:
        f = cohort["families"][fam]
        yaw = f["yaw_pct"]
        cte = f["cte_pct"]
        yaw_cell = f"{yaw['mean']:+.1f}% ± {yaw['std']:.1f}%" if yaw["n"] else "—"
        cte_cell = f"{cte['mean']:+.1f}% ± {cte['std']:.1f}%" if cte["n"] else "—"
        out.append(
            f"<tr><td><code>{fam}</code></td>"
            f"<td>{f['n_ok']}/{f['n_total']}</td>"
            f"<td class='{metric_class(yaw['mean'])}'>{yaw_cell}</td>"
            f"<td class='{metric_class(cte['mean'])}'>{cte_cell}</td>"
            f"<td>{f['n_failed']}</td></tr>"
        )
    out.append("</tbody></table></div>")
    return "\n".join(out)


def per_platform_table(cohort: dict) -> str:
    if not cohort.get("per_platform"):
        return ""
    out = [
        "<div class='table-wrap'><table><thead><tr>",
        "<th>platform</th><th>agents</th><th>yaw Δ% (mean ± σ)</th><th>CTE Δ% (mean ± σ)</th>",
        "</tr></thead><tbody>",
    ]
    for plat, blk in sorted(cohort["per_platform"].items()):
        y = blk["yaw_pct"]
        c = blk["cte_pct"]
        out.append(
            f"<tr><td><code>{plat}</code></td>"
            f"<td>{blk['n_agents']}</td>"
            f"<td class='{metric_class(y['mean'])}'>{y['mean']:+.1f}% ± {y['std']:.1f}%</td>"
            f"<td class='{metric_class(c['mean'])}'>{c['mean']:+.1f}% ± {c['std']:.1f}%</td></tr>"
        )
    out.append("</tbody></table></div>")
    return "\n".join(out)


def per_agent_table(cohort: dict) -> str:
    has_sr = cohort.get("self_reported_loaded")
    headers = (
        ["agent", "family", "status", "yaw Δ%", "CTE Δ%", "claimed yaw", "claimed CTE", "yaw gap", "CTE gap", "n seg", "wall"]
        if has_sr else
        ["agent", "family", "status", "yaw V0", "yaw final", "yaw Δ%", "CTE V0", "CTE final", "CTE Δ%", "n seg ok/total", "wall"]
    )
    out = ["<div class='table-wrap'><table><thead><tr>"]
    out += [f"<th>{h}</th>" for h in headers]
    out.append("</tr></thead><tbody>")
    for row in sorted(cohort["per_agent"], key=lambda r: (r["family"], r["agent_id"])):
        if row["status"] != "ok":
            reason = html.escape(row.get("reason") or "?")
            blanks = "<td>—</td>" * (len(headers) - 4)
            out.append(
                f"<tr><td><code>{row['agent_id']}</code></td>"
                f"<td><code>{row['family']}</code></td>"
                f"<td><span class='metric metric-bad'>{reason}</span></td>"
                f"{blanks}<td>{row.get('n_seg_ok','?')}/{row.get('n_seg_total','?')}</td><td>—</td></tr>"
            )
            continue
        if has_sr:
            cells = [
                f"<code>{row['agent_id']}</code>", f"<code>{row['family']}</code>", "ok",
                f"<span class='metric {metric_class(row['yaw_pct'])}'>{fmt_pct(row['yaw_pct'])}</span>",
                f"<span class='metric {metric_class(row['cte_pct'])}'>{fmt_pct(row['cte_pct'])}</span>",
                fmt_pct(row.get("claimed_yaw_pct")), fmt_pct(row.get("claimed_cte_pct")),
                fmt_pct(row.get("yaw_gap")), fmt_pct(row.get("cte_gap")),
                f"{row['n_seg_ok']}/{row['n_seg_total']}", f"{row['wall_seconds']}s",
            ]
        else:
            cells = [
                f"<code>{row['agent_id']}</code>", f"<code>{row['family']}</code>", "ok",
                fmt_n(row["yaw_baseline_rmse"], 6), fmt_n(row["yaw_agent_rmse"], 6),
                f"<span class='metric {metric_class(row['yaw_pct'])}'>{fmt_pct(row['yaw_pct'])}</span>",
                fmt_n(row["cte_baseline_m"], 2), fmt_n(row["cte_agent_m"], 2),
                f"<span class='metric {metric_class(row['cte_pct'])}'>{fmt_pct(row['cte_pct'])}</span>",
                f"{row['n_seg_ok']}/{row['n_seg_total']}", f"{row['wall_seconds']}s",
            ]
        out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    out.append("</tbody></table></div>")
    return "\n".join(out)


def calibration_cards(cohort: dict) -> str:
    coeffs = cohort.get("coefficients") or {}
    if not coeffs:
        return ""
    out = ["<div class='grid-2'>"]
    for aid in sorted(coeffs.keys()):
        body = json.dumps(coeffs[aid], indent=2)[:1200]
        out.append(
            f"<div class='card card-purple'><h3 style='margin:0 0 0.5rem 0;'><code>{aid}</code></h3>"
            f"<pre style='font-size:0.8rem;background:#f5f5f5;padding:0.6rem;border-radius:6px;overflow:auto;'>"
            f"{html.escape(body)}</pre></div>"
        )
    out.append("</div>")
    return "\n".join(out)


def reconstruction_section(cohort: dict) -> str:
    r = cohort["reconstruction"]
    rows = []
    for k in r["format_check_pass"]:
        passes = r["format_check_pass"][k]
        fails = r["format_check_fail"].get(k, 0)
        cls = "metric-good" if fails == 0 else ("metric-bad" if fails > passes else "")
        rows.append(f"<tr><td><code>{k}</code></td><td class='{cls}'>{passes}</td><td>{fails}</td></tr>")
    table = (
        "<div class='table-wrap'><table><thead><tr>"
        "<th>format check</th><th>pass</th><th>fail</th>"
        "</tr></thead><tbody>" + "".join(rows) + "</tbody></table></div>"
    )
    if r["failure_reasons"]:
        rl = "<ul>" + "".join(
            f"<li><code>{k}</code> — {v} agent(s)</li>"
            for k, v in sorted(r["failure_reasons"].items(), key=lambda kv: -kv[1])
        ) + "</ul>"
        table += f"<div class='critical'><strong>Failure reasons across the cohort:</strong>{rl}</div>"
    return table


def worst_section(cohort: dict) -> str:
    w = cohort["winners"]
    def lst(rows):
        return "<ul>" + "".join(f"<li><code>{a}</code> ({fmt_pct(v)})</li>" for a, v in rows) + "</ul>"
    return (
        "<div class='grid-2'>"
        f"<div class='card card-blue'><h3>Lowest yaw Δ%</h3>{lst(w['yaw_bot3'])}</div>"
        f"<div class='card card-orange'><h3>Lowest CTE Δ%</h3>{lst(w['cte_bot3'])}</div>"
        "</div>"
    )


def render(cohort: dict, *, interactive: bool) -> str:
    style_block, logo = extract_style_and_logo(STYLING_SKILL_LIGHT)
    bl = cohort["baseline"]
    run = cohort.get("run", {})
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    # Build the four figures.
    fig_scatter = chart.scatter_yaw_vs_cte(cohort)
    fig_family = chart.bars_per_family(cohort)
    fig_platform = chart.scatter_per_platform(cohort)
    fig_box = chart.boxplot_per_segment(cohort)

    if interactive:
        scatter_html = chart.to_interactive_html(fig_scatter, div_id="scatter-main")
        family_html  = chart.to_interactive_html(fig_family,  div_id="bars-family")
        platform_html = chart.to_interactive_html(fig_platform, div_id="scatter-platform")
        box_html = chart.to_interactive_html(fig_box, div_id="box-segments")
        plotly_cdn = '<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>'
    else:
        scatter_html = chart.to_static_svg(fig_scatter, width=1000, height=560)
        family_html  = chart.to_static_svg(fig_family, width=1000, height=420)
        platform_html = chart.to_static_svg(fig_platform, width=1000, height=420)
        box_html = chart.to_static_svg(fig_box, width=1100, height=520)
        plotly_cdn = ""

    headline = callout_headline(cohort)
    title = f"Cohort canonical evaluation — {cohort['n_agents_total']} agents"
    subtitle = f"{cohort['idea_id']} · {bl['n_segments']} held-out segments · V0 yaw {bl['yaw_rate']['rmse_rad_per_s']:.5f} rad/s, CTE {bl['cte']['rmse_meters']:.2f} m · generated {ts}"

    body = f"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(title)}</title>
{style_block}
<style>
/* iteration 2 — chart container tweaks */
.chart-wrap {{ background:#fff; border:1px solid #e5e5e5; border-radius:10px; padding:1rem; margin: 1rem 0; }}
.chart-wrap svg {{ max-width: 100%; height: auto; }}
.metric.metric-good {{ color:#0a8a3a; background:#e6f5ec; }}
.metric.metric-bad  {{ color:#b03030; background:#fce8e8; }}
.summary-grid {{ display:grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap:1rem; margin:1rem 0; }}
.summary-grid .stat {{ background:#fff; border:1px solid #e5e5e5; border-radius:10px; padding:0.8rem 1rem; }}
.summary-grid .stat .v {{ font-size:1.6rem; font-weight:700; color:#0a0b24; }}
.summary-grid .stat .l {{ font-size:0.85rem; color:#646471; text-transform:uppercase; letter-spacing:0.05em; }}
pre {{ font-family: 'JetBrains Mono', 'Menlo', monospace; }}
</style>
{plotly_cdn}
</head>
<body>

<header class="hero">
<div class="container">
{logo}
<h1>{html.escape(title)}</h1>
<p class="subtitle">{html.escape(subtitle)}</p>
</div>
</header>

<section class="section">
<div class="container">
<h2 class="accent-blue">Executive summary</h2>

<div class="summary-grid">
  <div class="stat"><div class="l">agents (ok / total)</div><div class="v">{cohort['n_ok']} / {cohort['n_agents_total']}</div></div>
  <div class="stat"><div class="l">eval pool</div><div class="v">{bl['n_segments']} segs</div></div>
  <div class="stat"><div class="l">V0 yaw RMSE</div><div class="v">{bl['yaw_rate']['rmse_rad_per_s']:.5f}</div></div>
  <div class="stat"><div class="l">V0 CTE RMSE</div><div class="v">{bl['cte']['rmse_meters']:.2f} m</div></div>
  <div class="stat"><div class="l">wall time</div><div class="v">{run.get('wall_time_seconds','?')}s</div></div>
</div>

<div class="key-finding">
<p>{headline}</p>
</div>
</div>
</section>

<section class="section section-alt">
<div class="container">
<h2 class="accent-purple">1. Headline scatter — yaw vs CTE improvement</h2>
<div class="card card-purple">
<p>Each agent is one point. <strong>Top-right is the goal</strong> — both KPIs improve over V0. The dashed diagonal is y = x: above it, an agent improved CTE more than yaw (good trajectory integration); below, the opposite. The V0 baseline sits at the origin.</p>
<div class="chart-wrap">{scatter_html}</div>
</div>
</div>
</section>

<section class="section">
<div class="container">
<h2 class="accent-orange">2. Module-level aggregation</h2>
<div class="card card-orange">
<p>Performance grouped by which module shipped the agent. Mean Δ% over only the agents that reconstructed successfully; failures shown separately.</p>
<div class="chart-wrap">{family_html}</div>
{family_table(cohort)}
</div>
</div>
</section>

<section class="section section-alt">
<div class="container">
<h2 class="accent-blue">3. Per-platform breakdown</h2>
<div class="card card-blue">
<p>Same cohort, but split by the vehicle platform the agent was evaluated on. Agents that win one platform but lose another have a platform-specific calibration; agents whose dots cluster together generalise.</p>
<div class="chart-wrap">{platform_html}</div>
{per_platform_table(cohort)}
</div>
</div>
</section>

<section class="section">
<div class="container">
<h2 class="accent-purple">4. Per-segment yaw RMSE distribution</h2>
<div class="card card-purple">
<p>Each box summarises one agent's per-segment yaw RMSE — pooled RMSE can hide that an agent does great on most segments but pathologically badly on a few. The y-axis is logarithmic to compress outliers.</p>
<div class="chart-wrap">{box_html}</div>
</div>
</div>
</section>

<section class="section section-alt">
<div class="container">
<h2 class="accent-orange">5. Per-agent canonical scorecard</h2>
<div class="card card-orange">
<p>The full table. Failed reconstructions are surfaced with their reason — no fake zeros.</p>
{per_agent_table(cohort)}
</div>
</div>
</section>

<section class="section">
<div class="container">
<h2 class="accent-blue">6. Calibration cards — fitted coefficients</h2>
<div class="card card-blue">
<p>Where the cohort converges on similar physics, and where it forks. Each tile is one agent's <code>coeffs.json</code> as shipped.</p>
{calibration_cards(cohort)}
</div>
</div>
</section>

<section class="section section-alt">
<div class="container">
<h2 class="accent-purple">7. Reconstruction quality (substrate signal)</h2>
<div class="card card-purple">
<p>How many agents shipped the right artefacts to be canonically gradable. Failures here are a substrate or contract problem, not a model problem.</p>
{reconstruction_section(cohort)}
</div>
</div>
</section>

<section class="section">
<div class="container">
<h2 class="accent-orange">8. Worst-of-cohort</h2>
{worst_section(cohort)}
</div>
</section>

<footer class="footer">
<p>Generated by <code>grade-cohort-reports</code> at {ts} · idea <code>{cohort['idea_id']}</code></p>
</footer>

</body>
</html>
"""
    return body


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--grade-dir", type=Path, required=True)
    p.add_argument("--print-only", action="store_true", help="render only the static print version")
    args = p.parse_args()

    cohort_path = args.grade_dir / "cohort.json"
    if not cohort_path.is_file():
        sys.exit(f"report_html: missing {cohort_path}")
    cohort = json.loads(cohort_path.read_text())

    if not args.print_only:
        out_html = args.grade_dir / "cohort.html"
        out_html.write_text(render(cohort, interactive=True))
        print(f"report_html: cohort.html -> {out_html}")

    out_print = args.grade_dir / "cohort.print.html"
    out_print.write_text(render(cohort, interactive=False))
    print(f"report_html: cohort.print.html -> {out_print}")


if __name__ == "__main__":
    main()
