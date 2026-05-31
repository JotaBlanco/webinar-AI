#!/usr/bin/env python3
"""Render cohort.md from cohort.json.

Iteration 1: Markdown only.
Iteration 2 will add HTML + PDF (via quix-report-styling) + plotly scatter.

This file is intentionally dumb — every number it prints comes from cohort.json
already. No statistics computed here; renderer only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def fmt_pct(v):
    if v is None:
        return "—"
    return f"{v:+.1f}%"


def fmt_n(v, digits=4):
    if v is None:
        return "—"
    return f"{v:.{digits}f}"


def fmt_stats_pct(s: dict) -> str:
    if s["n"] == 0:
        return "_n=0_"
    return f"{s['mean']:+.1f}% ± {s['std']:.1f}% (med {s['median']:+.1f}%)"


def render(cohort: dict) -> str:
    out: list[str] = []
    bl = cohort["baseline"]
    run = cohort.get("run", {})

    out.append(f"# Cohort canonical evaluation — {cohort['n_agents_total']} agents")
    out.append("")
    out.append(f"- **idea**: `{cohort['idea_id']}`")
    out.append(f"- **eval pool**: {bl['n_segments']} held-out segments under `{bl['eval_data_root']}`")
    out.append(f"- **V0 baselines**: yaw RMSE = **{bl['yaw_rate']['rmse_rad_per_s']:.6f} rad/s** "
               f"({bl['yaw_rate']['n_samples_after_filter']:,} samples); "
               f"CTE RMSE = **{bl['cte']['rmse_meters']:.4f} m** "
               f"({bl['cte']['n_distance_bins']:,} bins)")
    out.append(f"- **reconstructed**: {cohort['n_ok']} ok / {cohort['n_failed']} failed "
               f"(wall {run.get('wall_time_seconds','?')}s, concurrency {run.get('concurrency','?')})")
    out.append("")

    w = cohort["winners"]
    out.append("## Headline")
    out.append("")
    if w["yaw_top3"]:
        a, v = w["yaw_top3"][0]
        out.append(f"- 🥇 **Best yaw**: `{a}` ({fmt_pct(v)})")
    if w["cte_top3"]:
        a, v = w["cte_top3"][0]
        out.append(f"- 🥇 **Best CTE**: `{a}` ({fmt_pct(v)})")
    if w["double_30"]:
        out.append(f"- 🎯 **Winning both KPIs ≥ +30%** ({len(w['double_30'])} agents): " +
                   ", ".join(f"`{a}`" for a in w["double_30"]))
    elif w["double_25"]:
        out.append(f"- 🎯 **Winning both KPIs ≥ +25%** ({len(w['double_25'])} agents): " +
                   ", ".join(f"`{a}`" for a in w["double_25"]))
    out.append("")

    out.append("## Performance by family")
    out.append("")
    out.append("Each family is a comparison group (e.g. `module-N`). Improvement %s computed against the SAME V0 baseline on the SAME held-out pool.")
    out.append("")
    out.append("| family | n ok / total | yaw Δ% (mean ± σ) | CTE Δ% (mean ± σ) | failures |")
    out.append("|---|---|---|---|---|")
    for fam in cohort["family_order"]:
        f = cohort["families"][fam]
        out.append(f"| `{fam}` | {f['n_ok']}/{f['n_total']} | {fmt_stats_pct(f['yaw_pct'])} | {fmt_stats_pct(f['cte_pct'])} | {f['n_failed']} |")
    out.append("")

    if cohort["per_platform"]:
        out.append("## Per-platform breakdown")
        out.append("")
        out.append("How each platform fared when supported. Mean across all agents that declared support AND ran successfully on that platform.")
        out.append("")
        out.append("| platform | agents | yaw Δ% (mean ± σ) | CTE Δ% (mean ± σ) |")
        out.append("|---|---|---|---|")
        for plat, blk in sorted(cohort["per_platform"].items()):
            out.append(f"| `{plat}` | {blk['n_agents']} | {fmt_stats_pct(blk['yaw_pct'])} | {fmt_stats_pct(blk['cte_pct'])} |")
        out.append("")

    out.append("## Per-agent canonical scorecard")
    out.append("")
    has_sr = cohort.get("self_reported_loaded")
    if has_sr:
        out.append("| agent | family | status | yaw Δ% | CTE Δ% | claimed yaw | claimed CTE | yaw gap | CTE gap | n seg | wall |")
        out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    else:
        out.append("| agent | family | status | yaw V0 | yaw final | yaw Δ% | CTE V0 | CTE final | CTE Δ% | n seg ok/total | wall |")
        out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for row in sorted(cohort["per_agent"], key=lambda r: (r["family"], r["agent_id"])):
        if row["status"] != "ok":
            reason = row.get("reason") or "?"
            out.append(f"| `{row['agent_id']}` | `{row['family']}` | ❌ **{reason}** | — | — | — | — | — | — | {row.get('n_seg_ok','?')}/{row.get('n_seg_total','?')} | — |")
            continue
        if has_sr:
            out.append(
                f"| `{row['agent_id']}` | `{row['family']}` | ok | "
                f"**{fmt_pct(row['yaw_pct'])}** | **{fmt_pct(row['cte_pct'])}** | "
                f"{fmt_pct(row.get('claimed_yaw_pct'))} | {fmt_pct(row.get('claimed_cte_pct'))} | "
                f"{fmt_pct(row.get('yaw_gap'))} | {fmt_pct(row.get('cte_gap'))} | "
                f"{row['n_seg_ok']}/{row['n_seg_total']} | {row['wall_seconds']}s |"
            )
        else:
            out.append(
                f"| `{row['agent_id']}` | `{row['family']}` | ok | "
                f"{fmt_n(row['yaw_baseline_rmse'], 6)} | {fmt_n(row['yaw_agent_rmse'], 6)} | **{fmt_pct(row['yaw_pct'])}** | "
                f"{fmt_n(row['cte_baseline_m'], 2)} | {fmt_n(row['cte_agent_m'], 2)} | **{fmt_pct(row['cte_pct'])}** | "
                f"{row['n_seg_ok']}/{row['n_seg_total']} | {row['wall_seconds']}s |"
            )
    out.append("")

    if cohort.get("per_segment"):
        out.append("## Per-segment yaw-RMSE distribution (spread within each agent)")
        out.append("")
        out.append("Pooled RMSE can hide that an agent is great on most segments but pathological on a few. These columns expose that.")
        out.append("")
        out.append("| agent | n segs | min | median | mean | max | std |")
        out.append("|---|---|---|---|---|---|---|")
        for aid in sorted(cohort["per_segment"].keys()):
            s = cohort["per_segment"][aid]["yaw_segment_rmse"]
            if s["n"] == 0:
                continue
            out.append(f"| `{aid}` | {s['n']} | {fmt_n(s['min'], 4)} | {fmt_n(s['median'], 4)} | {fmt_n(s['mean'], 4)} | {fmt_n(s['max'], 4)} | {fmt_n(s['std'], 4)} |")
        out.append("")

    if cohort.get("coefficients"):
        out.append("## Calibration cards (agent-reported coefficients)")
        out.append("")
        out.append("Where the cohort converges on similar physics vs where it forks. Flattened from each agent's `coeffs.json`.")
        out.append("")
        for aid in sorted(cohort["coefficients"].keys()):
            coeffs = cohort["coefficients"][aid]
            out.append(f"### `{aid}`")
            out.append("```json")
            out.append(json.dumps(coeffs, indent=2)[:1200])
            out.append("```")
            out.append("")

    r = cohort["reconstruction"]
    out.append("## Reconstruction quality (substrate signal)")
    out.append("")
    out.append("How many agents shipped the right artefacts to be canonically gradable. Failures here are a substrate / contract problem, not a model problem.")
    out.append("")
    out.append("| format check | pass | fail |")
    out.append("|---|---|---|")
    for k in r["format_check_pass"]:
        out.append(f"| `{k}` | {r['format_check_pass'][k]} | {r['format_check_fail'].get(k, 0)} |")
    out.append("")
    if r["failure_reasons"]:
        out.append("**Failure reasons** (across the cohort):")
        out.append("")
        for reason, count in sorted(r["failure_reasons"].items(), key=lambda kv: -kv[1]):
            out.append(f"- `{reason}` — {count} agent(s)")
        out.append("")

    out.append("## Worst-of-cohort (among ok submissions)")
    out.append("")
    if w["yaw_bot3"]:
        out.append("**Lowest yaw Δ%**:")
        for a, v in w["yaw_bot3"]:
            out.append(f"- `{a}` ({fmt_pct(v)})")
        out.append("")
    if w["cte_bot3"]:
        out.append("**Lowest CTE Δ%**:")
        for a, v in w["cte_bot3"]:
            out.append(f"- `{a}` ({fmt_pct(v)})")
        out.append("")

    return "\n".join(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--grade-dir", type=Path, required=True)
    args = p.parse_args()

    cohort_path = args.grade_dir / "cohort.json"
    if not cohort_path.is_file():
        sys.exit(f"report: missing {cohort_path} — run aggregate.py first")
    cohort = json.loads(cohort_path.read_text())

    md = render(cohort)
    out_md = args.grade_dir / "cohort.md"
    out_md.write_text(md)
    print(f"report: cohort.md -> {out_md} ({len(md):,} chars)")


if __name__ == "__main__":
    main()
