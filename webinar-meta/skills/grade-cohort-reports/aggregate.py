#!/usr/bin/env python3
"""Aggregate per-agent grading JSONs into a cohort summary.

Reads:
    <grade-dir>/raw/<agent_id>.json      # one strict-JSON file per agent (parent persists subagent output here)
    <grade-dir>/rubric-snapshot.yaml     # the rubric at grading time
    <grade-dir>/manifest.json            # optional per-report metadata (substrate components etc.)

Writes:
    <grade-dir>/per-agent/<agent_id>.md  # human-readable per-agent scorecard
    <grade-dir>/cohort.json              # machine-readable cohort summary
    <grade-dir>/cohort.md                # human-readable cohort summary
"""

import argparse
import json
import math
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path


def load_raw(grade_dir: Path) -> list[dict]:
    raw_dir = grade_dir / "raw"
    if not raw_dir.is_dir():
        sys.exit(f"aggregate: missing {raw_dir} — parent must persist judge JSONs here, one per agent")
    out = []
    for f in sorted(raw_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text())
        except json.JSONDecodeError as e:
            print(f"aggregate: WARN — {f.name} is not valid JSON: {e}", file=sys.stderr)
            continue
        out.append(data)
    if not out:
        sys.exit(f"aggregate: no parseable judge outputs in {raw_dir}")
    return out


def render_per_agent_md(card: dict) -> str:
    lines = [f"# {card['agent_id']}", "",
             f"Report: `{card.get('report_path','?')}`", ""]
    headline = card.get("headline", {}) or {}
    lines.append("## Headline (as the agent reported)")
    for k in ("primary_metric", "platform", "baseline_value", "final_value", "improvement", "top_contributor"):
        v = headline.get(k)
        lines.append(f"- **{k}**: {v if v is not None else '_not stated_'}")
    lines.append("")

    flags = card.get("honesty_flags", {}) or {}
    lines.append("## Honesty flags")
    for k, v in flags.items():
        lines.append(f"- **{k}**: `{v}`")
    lines.append("")

    lines.append("## Rubric items")
    lines.append("")
    lines.append("| id | type | result | threshold met | evidence |")
    lines.append("|---|---|---|---|---|")
    for item in card.get("items", []):
        rid = item.get("id", "?")
        rtype = item.get("type", "?")
        result = item.get("result")
        tmet = item.get("threshold_met")
        ev = item.get("evidence", []) or []
        ev_str = "; ".join(f'"{e[:80]}…"' if len(e) > 80 else f'"{e}"' for e in ev) or "_none_"
        lines.append(f"| {rid} | {rtype} | {result} | {tmet} | {ev_str} |")
    lines.append("")

    lines.append("## Per-item reasoning")
    for item in card.get("items", []):
        lines.append(f"### {item.get('id','?')}")
        lines.append(f"- result: `{item.get('result')}`")
        if item.get("type") == "numeric":
            lines.append(f"- value: `{item.get('value')}`, threshold_met: `{item.get('threshold_met')}`")
        lines.append(f"- reasoning: {item.get('reasoning','')}")
        ev = item.get("evidence", []) or []
        if ev:
            lines.append("- evidence:")
            for q in ev:
                lines.append(f"  > {q}")
        else:
            lines.append("- evidence: _none_")
        lines.append("")
    return "\n".join(lines)


def _family_stats(values: list[float]) -> dict:
    """Mean / median / std / min / max over a list of numeric values. NaNs and Nones excluded."""
    clean = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not clean:
        return {"n": 0, "mean": None, "median": None, "std": None, "min": None, "max": None}
    return {
        "n": len(clean),
        "mean": round(statistics.fmean(clean), 3),
        "median": round(statistics.median(clean), 3),
        "std": round(statistics.pstdev(clean), 3) if len(clean) >= 2 else 0.0,
        "min": round(min(clean), 3),
        "max": round(max(clean), 3),
    }


def _fmt_stats(s: dict, unit: str = "") -> str:
    if s["n"] == 0:
        return "_n=0_"
    return (f"n={s['n']}, mean={s['mean']}{unit}, median={s['median']}{unit}, "
            f"std={s['std']}{unit}, [{s['min']}{unit} … {s['max']}{unit}]")


def render_family_section(cards: list[dict], families: dict[str, str]) -> tuple[list[str], dict]:
    """Per-family aggregation: rubric pass rate, improvement stats, honesty counts."""
    by_fam: dict[str, list[dict]] = defaultdict(list)
    for card in cards:
        fam = families.get(card.get("agent_id", ""), "unknown")
        by_fam[fam].append(card)

    # Stable family order: 'raw' first, then alphabetical.
    fam_order = sorted(by_fam.keys(), key=lambda f: (f != "raw", f))

    # Collect all rubric ids across cohort (preserve first-seen order).
    rubric_ids: list[str] = []
    seen_ids: set[str] = set()
    for card in cards:
        for it in card.get("items", []):
            rid = it.get("id")
            if rid and rid not in seen_ids:
                seen_ids.add(rid)
                rubric_ids.append(rid)

    out: list[str] = []
    cohort_json: dict = {"families": {}, "order": fam_order, "rubric_ids": rubric_ids}

    # ---- Per-family summary table ----
    out.append("## Per-family performance & variance")
    out.append("")
    out.append("Each family is one comparison group (e.g. `raw` = the naked baseline; `angle-A/module-3` = "
               "module-3 of angle A). Improvement % uses the judge's `improvement_pct_numeric` extraction "
               "(positive = better, regardless of whether lower-is-better on the underlying metric).")
    out.append("")
    out.append("| family | n | rubric pass rate (mean per agent) | improvement % (mean) | improvement % (median) | improvement % (std) | range |")
    out.append("|---|---|---|---|---|---|---|")
    for fam in fam_order:
        cs = by_fam[fam]
        # Pass rate: per agent, fraction of binary items that passed (non-null denominator).
        per_agent_rate: list[float] = []
        for c in cs:
            items = c.get("items", []) or []
            denom = sum(1 for it in items if it.get("result") in (True, False))
            passes = sum(1 for it in items if it.get("result") is True)
            per_agent_rate.append(passes / denom if denom else 0.0)
        pr_stats = _family_stats(per_agent_rate)
        imp = [(c.get("headline", {}) or {}).get("improvement_pct_numeric") for c in cs]
        imp_stats = _family_stats(imp)
        pr_cell = "_n=0_" if pr_stats["n"] == 0 else f"{pr_stats['mean']:.0%} ± {pr_stats['std']:.0%}"
        if imp_stats["n"]:
            rng_cell = f"{imp_stats['min']:+.1f}% … {imp_stats['max']:+.1f}%"
            mean_cell = f"{imp_stats['mean']:+.1f}%"
            med_cell = f"{imp_stats['median']:+.1f}%"
            std_cell = f"{imp_stats['std']:.1f}%"
        else:
            rng_cell = mean_cell = med_cell = std_cell = "_n=0_"
        out.append(f"| `{fam}` | {len(cs)} | {pr_cell} | {mean_cell} | {med_cell} | {std_cell} | {rng_cell} |")
        cohort_json["families"][fam] = {
            "n": len(cs),
            "agent_ids": [c.get("agent_id") for c in cs],
            "rubric_pass_rate_per_agent": pr_stats,
            "improvement_pct": imp_stats,
        }
    out.append("")

    # ---- Per-rubric pass rate matrix (families as columns) ----
    out.append("## Per-rubric pass rate by family (PASS / scored — nulls excluded)")
    out.append("")
    header = "| rubric item | " + " | ".join(f"`{f}`" for f in fam_order) + " |"
    sep = "|---|" + "|".join("---" for _ in fam_order) + "|"
    out.append(header)
    out.append(sep)
    per_item_per_fam: dict[str, dict[str, dict]] = defaultdict(dict)
    for rid in rubric_ids:
        row_cells = []
        for fam in fam_order:
            cs = by_fam[fam]
            results = []
            for c in cs:
                for it in c.get("items", []):
                    if it.get("id") == rid:
                        results.append(it.get("result"))
                        break
                else:
                    results.append(None)
            passes = sum(1 for r in results if r is True)
            fails = sum(1 for r in results if r is False)
            nulls = sum(1 for r in results if r is None)
            denom = passes + fails
            cell = f"{passes}/{denom}" if denom else f"–/0 ({nulls} null)"
            if denom:
                cell = f"{passes}/{denom} ({passes/denom:.0%})"
            row_cells.append(cell)
            per_item_per_fam[rid][fam] = {"pass": passes, "fail": fails, "null": nulls,
                                           "rate": (passes/denom) if denom else None}
        out.append(f"| `{rid}` | " + " | ".join(row_cells) + " |")
    out.append("")
    cohort_json["per_item_per_family"] = per_item_per_fam

    # ---- Honesty per family ----
    out.append("## Honesty flags by family")
    out.append("")
    out.append("| family | declared limitations (mean per agent) | named data gap | fabricated proxy undeclared |")
    out.append("|---|---|---|---|")
    for fam in fam_order:
        cs = by_fam[fam]
        decls = [int((c.get("honesty_flags", {}) or {}).get("declared_limitations", 0) or 0) for c in cs]
        gap = sum(1 for c in cs if (c.get("honesty_flags", {}) or {}).get("named_data_gap_or_missing_truth_channel"))
        fab = sum(1 for c in cs if (c.get("honesty_flags", {}) or {}).get("fabricated_truth_or_proxy_undeclared"))
        mean_decl = (sum(decls) / len(decls)) if decls else 0
        out.append(f"| `{fam}` | {mean_decl:.1f} | {gap}/{len(cs)} | {fab}/{len(cs)} |")
        cohort_json["families"][fam]["honesty"] = {
            "mean_declared_per_agent": round(mean_decl, 2),
            "named_data_gap": gap,
            "fabricated_undeclared": fab,
        }
    out.append("")

    return out, cohort_json


def _yaw_block(c: dict) -> dict:
    """Pull the yaw_rate sub-block, falling back to legacy top-level fields."""
    yr = c.get("yaw_rate")
    if isinstance(yr, dict):
        return yr
    # Legacy / failed-status agents — synthesise from top-level.
    return {
        "baseline_rmse": c.get("baseline_rmse"),
        "agent_rmse": c.get("agent_rmse"),
        "improvement_pct": c.get("improvement_pct"),
        "n_samples_after_filter": c.get("n_samples_after_filter"),
    }


def _cte_block(c: dict) -> dict | None:
    """Pull the cte sub-block. Returns None for agents graded before CTE existed."""
    cte = c.get("cte")
    return cte if isinstance(cte, dict) else None


def _family_stats(values: list[float]) -> dict:
    return {
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "std": statistics.pstdev(values) if len(values) >= 2 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def render_canonical_section(canonical: list[dict], families: dict[str, str]) -> tuple[list[str], dict]:
    """Render the canonical headline section + per-family canonical performance for both KPIs."""
    by_fam: dict[str, list[dict]] = defaultdict(list)
    for c in canonical:
        fam = families.get(c.get("agent_id", ""), "unknown")
        by_fam[fam].append(c)
    fam_order = sorted(by_fam.keys(), key=lambda f: (f != "raw", f))

    out: list[str] = []
    cohort_json: dict = {"families": {}, "per_agent": []}

    # Pull V0 baselines (constant across all agents — use the first OK one).
    v0_yaw = None
    v0_cte = None
    cte_available = False
    for c in canonical:
        if c.get("status") != "ok":
            continue
        yr = _yaw_block(c)
        if v0_yaw is None and yr.get("baseline_rmse") is not None:
            v0_yaw = yr["baseline_rmse"]
        cte = _cte_block(c)
        if cte:
            cte_available = True
            if v0_cte is None and cte.get("baseline_rmse_meters") is not None:
                v0_cte = cte["baseline_rmse_meters"]
        if v0_yaw is not None and (v0_cte is not None or not cte_available):
            break
    if v0_yaw is None and canonical:
        # All failed — fall back to top-level baseline_rmse on the first card.
        v0_yaw = canonical[0].get("baseline_rmse")

    n_total = len(canonical)
    n_ok = sum(1 for c in canonical if c.get("status") == "ok")
    n_failed = n_total - n_ok

    out.append("## Canonical evaluation — each agent's model re-run against the fixed eval set")
    out.append("")
    out.append("Two primary KPIs. `yaw-rate RMSE` measures instantaneous fidelity; `CTE RMSE` measures cumulative trajectory drift over distance. A model that wins one but loses the other has a known signature (see best-practices.md).")
    out.append("")
    if v0_yaw is not None:
        out.append(f"- V0 yaw-rate baseline: **{v0_yaw:.6f} rad/s**")
    if cte_available and v0_cte is not None:
        out.append(f"- V0 CTE baseline: **{v0_cte:.4f} m** (distance-resampled, 1m grid, ≥20m segments)")
    out.append(f"- Agents successfully re-run: **{n_ok}/{n_total}**" + (f" — {n_failed} failed reconstruction" if n_failed else ""))
    out.append("")

    # ---- Per-family canonical performance & variance — yaw-rate ----
    out.append("### Per-family canonical performance — KPI 1: yaw-rate RMSE")
    out.append("")
    out.append("Cross-agent comparison: every agent's favourite model run against the SAME held-out Ford segments, "
               "scored against the SAME truth channel, with the SAME V0 baseline. "
               "`Δ% = (V0_RMSE - agent_RMSE) / V0_RMSE * 100`. Positive = better.")
    out.append("")
    out.append("| family | n ok / total | mean Δ% vs V0 | median Δ% | std Δ% | range |")
    out.append("|---|---|---|---|---|---|")
    for fam in fam_order:
        cs = by_fam[fam]
        ok = [c for c in cs if c.get("status") == "ok"]
        imp = [_yaw_block(c).get("improvement_pct") for c in ok]
        imp = [v for v in imp if v is not None]
        fam_entry: dict = cohort_json["families"].setdefault(fam, {"n_total": len(cs)})
        if not imp:
            out.append(f"| `{fam}` | 0/{len(cs)} | _n=0_ | _n=0_ | _n=0_ | _n=0_ |")
            fam_entry["yaw_rate"] = {"n_ok": 0, "improvement_pct": None}
            continue
        s = _family_stats(imp)
        out.append(f"| `{fam}` | {len(imp)}/{len(cs)} | {s['mean']:+.1f}% | {s['median']:+.1f}% | "
                   f"{s['std']:.1f}% | {s['min']:+.1f}% … {s['max']:+.1f}% |")
        fam_entry["yaw_rate"] = {
            "n_ok": len(imp),
            "improvement_pct": {"mean": round(s["mean"], 3), "median": round(s["median"], 3),
                                "std": round(s["std"], 3), "min": round(s["min"], 3), "max": round(s["max"], 3)},
        }
    out.append("")

    # ---- Per-family canonical performance & variance — CTE ----
    if cte_available:
        out.append("### Per-family canonical performance — KPI 2: cross-track-error RMSE")
        out.append("")
        out.append("Same cohort, same held-out segments, distance-resampled CTE in meters. "
                   "`Δ% = (V0_CTE - agent_CTE) / V0_CTE * 100`. Positive = better.")
        out.append("")
        out.append("| family | n ok / total | mean Δ% vs V0 | median Δ% | std Δ% | range |")
        out.append("|---|---|---|---|---|---|")
        for fam in fam_order:
            cs = by_fam[fam]
            ok = [c for c in cs if c.get("status") == "ok"]
            imp = [(_cte_block(c) or {}).get("improvement_pct") for c in ok]
            imp = [v for v in imp if v is not None]
            fam_entry = cohort_json["families"].setdefault(fam, {"n_total": len(cs)})
            if not imp:
                out.append(f"| `{fam}` | 0/{len(cs)} | _n=0_ | _n=0_ | _n=0_ | _n=0_ |")
                fam_entry["cte"] = {"n_ok": 0, "improvement_pct": None}
                continue
            s = _family_stats(imp)
            out.append(f"| `{fam}` | {len(imp)}/{len(cs)} | {s['mean']:+.1f}% | {s['median']:+.1f}% | "
                       f"{s['std']:.1f}% | {s['min']:+.1f}% … {s['max']:+.1f}% |")
            fam_entry["cte"] = {
                "n_ok": len(imp),
                "improvement_pct": {"mean": round(s["mean"], 3), "median": round(s["median"], 3),
                                    "std": round(s["std"], 3), "min": round(s["min"], 3), "max": round(s["max"], 3)},
            }
        out.append("")

    # ---- Per-agent canonical table — both KPIs side by side ----
    out.append("### Per-agent canonical headline (replaces self-reported)")
    out.append("")
    if cte_available:
        out.append("| agent | family | status | yaw V0 (rad/s) | yaw agent | yaw Δ% | CTE V0 (m) | CTE agent | CTE Δ% | reconstruction | notes |")
        out.append("|---|---|---|---|---|---|---|---|---|---|---|")
    else:
        out.append("| agent | family | status | baseline RMSE | agent RMSE | Δ% vs V0 | reconstruction | notes |")
        out.append("|---|---|---|---|---|---|---|---|")
    for c in sorted(canonical, key=lambda c: (families.get(c.get("agent_id", ""), "zz"), c.get("agent_id", ""))):
        aid = c.get("agent_id", "?")
        fam = families.get(aid, "unknown")
        st = c.get("status", "?")
        yr = _yaw_block(c)
        cte = _cte_block(c)
        method = c.get("reconstruction_method", "?")
        notes = (c.get("notes") or "")[:80]
        br = yr.get("baseline_rmse")
        ar = yr.get("agent_rmse")
        ip = yr.get("improvement_pct")
        if st == "ok":
            if cte_available:
                cbr = (cte or {}).get("baseline_rmse_meters")
                car = (cte or {}).get("agent_rmse_meters")
                cip = (cte or {}).get("improvement_pct")
                cbr_s = f"{cbr:.4f}" if cbr is not None else "—"
                car_s = f"{car:.4f}" if car is not None else "—"
                cip_s = f"**{cip:+.1f}%**" if cip is not None else "—"
                out.append(f"| **{aid}** | `{fam}` | ok | {br:.6f} | {ar:.6f} | **{ip:+.1f}%** | "
                           f"{cbr_s} | {car_s} | {cip_s} | {method} | {notes} |")
            else:
                out.append(f"| **{aid}** | `{fam}` | ok | {br:.6f} | {ar:.6f} | **{ip:+.1f}%** | {method} | {notes} |")
        else:
            reason = c.get("reason") or "?"
            br_cell = f"{br:.6f}" if br is not None else "?"
            if cte_available:
                out.append(f"| **{aid}** | `{fam}` | **FAILED** | {br_cell} | – | – | – | – | – | failed | {reason[:80]} |")
            else:
                out.append(f"| **{aid}** | `{fam}` | **FAILED** | {br_cell} | – | – | failed | {reason[:80]} |")
        per_agent_entry = {
            "agent_id": aid, "family": fam, "status": st,
            "yaw_rate": {"baseline_rmse": br, "agent_rmse": ar, "improvement_pct": ip},
            "reconstruction_method": method,
        }
        if cte:
            per_agent_entry["cte"] = {
                "baseline_rmse_meters": cte.get("baseline_rmse_meters"),
                "agent_rmse_meters": cte.get("agent_rmse_meters"),
                "improvement_pct": cte.get("improvement_pct"),
            }
        cohort_json["per_agent"].append(per_agent_entry)
    out.append("")

    return out, cohort_json


def render_cohort_md(cards: list[dict], rubric_yaml: str, manifest: dict, families: dict[str, str] | None = None,
                     canonical: list[dict] | None = None) -> tuple[str, dict]:
    out_lines: list[str] = []
    cohort_json: dict = {"n_agents": len(cards), "per_item": {}, "headline": [], "convergence": {}, "honesty": {}}

    out_lines.append(f"# Cohort grading — {len(cards)} agents")
    out_lines.append("")

    # ---- Per-family section (only if families.json was provided) ----
    if families:
        fam_lines, fam_json = render_family_section(cards, families)
        out_lines.extend(fam_lines)
        cohort_json["by_family"] = fam_json
        out_lines.append("")

    # ---- Canonical-eval section (only if canonical results exist) ----
    if canonical and families:
        canon_lines, canon_json = render_canonical_section(canonical, families)
        out_lines.extend(canon_lines)
        cohort_json["canonical"] = canon_json
        out_lines.append("")

    # ---- per-item pass rate ----
    item_results: dict[str, list] = defaultdict(list)
    for card in cards:
        for item in card.get("items", []):
            item_results[item["id"]].append(item.get("result"))
    out_lines.append("## Rubric pass rate (per item)")
    out_lines.append("")
    out_lines.append("| rubric item | pass | fail | null | pass rate |")
    out_lines.append("|---|---|---|---|---|")
    for rid, results in item_results.items():
        passes = sum(1 for r in results if r is True)
        fails = sum(1 for r in results if r is False)
        nulls = sum(1 for r in results if r is None)
        denom = passes + fails  # exclude nulls from pass rate
        rate = f"{passes}/{denom} = {passes/denom:.0%}" if denom else "n/a"
        out_lines.append(f"| `{rid}` | {passes} | {fails} | {nulls} | {rate} |")
        cohort_json["per_item"][rid] = {"pass": passes, "fail": fails, "null": nulls, "rate": rate}
    out_lines.append("")

    # ---- headline table ----
    out_lines.append("## Headline numbers (verbatim from each agent — NOT normalised)")
    out_lines.append("")
    out_lines.append("| agent | platform | primary metric | baseline | final | improvement | top contributor |")
    out_lines.append("|---|---|---|---|---|---|---|")
    for card in cards:
        h = card.get("headline", {}) or {}
        out_lines.append(
            f"| **{card['agent_id']}** | {h.get('platform','?')} | {h.get('primary_metric','?')} | "
            f"{h.get('baseline_value','?')} | {h.get('final_value','?')} | {h.get('improvement','?')} | "
            f"{h.get('top_contributor','?')} |"
        )
        cohort_json["headline"].append({"agent_id": card["agent_id"], **h})
    out_lines.append("")

    # ---- convergence ----
    out_lines.append("## Cohort convergence")
    out_lines.append("")
    for field in ("platform", "primary_metric", "top_contributor"):
        vals = Counter()
        for card in cards:
            v = (card.get("headline", {}) or {}).get(field)
            if v:
                vals[v] += 1
        out_lines.append(f"**{field}**")
        for v, n in vals.most_common():
            out_lines.append(f"- `{v}` — {n}/{len(cards)}")
        out_lines.append("")
        cohort_json["convergence"][field] = dict(vals)

    # ---- honesty ----
    out_lines.append("## Honesty flags")
    out_lines.append("")
    declared = [int((c.get("honesty_flags", {}) or {}).get("declared_limitations", 0) or 0) for c in cards]
    named_gap = sum(1 for c in cards if (c.get("honesty_flags", {}) or {}).get("named_data_gap_or_missing_truth_channel"))
    fabricated_undeclared = sum(1 for c in cards if (c.get("honesty_flags", {}) or {}).get("fabricated_truth_or_proxy_undeclared"))
    out_lines.append(f"- declared limitations per agent: min={min(declared)}, median={sorted(declared)[len(declared)//2]}, max={max(declared)}")
    out_lines.append(f"- named a data gap / missing truth channel: {named_gap}/{len(cards)}")
    out_lines.append(f"- ⚠️ fabricated truth/proxy WITHOUT declaring it: {fabricated_undeclared}/{len(cards)}")
    cohort_json["honesty"] = {
        "declared_per_agent": declared,
        "named_gap_count": named_gap,
        "fabricated_undeclared_count": fabricated_undeclared,
    }
    out_lines.append("")

    # ---- trap-trip narrative ----
    out_lines.append("## Trap-trip hotspots (rubric items most agents missed)")
    out_lines.append("")
    sorted_items = sorted(item_results.items(),
                          key=lambda kv: (sum(1 for r in kv[1] if r is False), -sum(1 for r in kv[1] if r is True)),
                          reverse=True)
    for rid, results in sorted_items[:3]:
        fails = sum(1 for r in results if r is False)
        if fails == 0:
            continue
        out_lines.append(f"- `{rid}`: {fails}/{len(cards)} agents failed")
    out_lines.append("")

    # ---- substrate column if manifest provided ----
    if manifest:
        out_lines.append("## Substrate descriptors (from manifest.json)")
        out_lines.append("")
        out_lines.append("| agent | descriptor |")
        out_lines.append("|---|---|")
        for card in cards:
            rp = card.get("report_path", "")
            desc = manifest.get(rp) or manifest.get(card["agent_id"]) or "_none_"
            out_lines.append(f"| {card['agent_id']} | {desc} |")
        out_lines.append("")

    return "\n".join(out_lines), cohort_json


SKILL_DIR = Path(__file__).resolve().parent


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--grade-dir", type=Path, required=True)
    p.add_argument("--no-pdf", action="store_true",
                   help="Skip cohort.pdf generation (default: PDF auto-generated via report.py)")
    args = p.parse_args()

    cards = load_raw(args.grade_dir)
    rubric_yaml = ""
    rs = args.grade_dir / "rubric-snapshot.yaml"
    if rs.is_file():
        rubric_yaml = rs.read_text()

    manifest: dict = {}
    mf = args.grade_dir / "manifest.json"
    if mf.is_file():
        try:
            manifest = json.loads(mf.read_text())
        except json.JSONDecodeError:
            print(f"aggregate: WARN — manifest.json is not valid JSON, ignoring", file=sys.stderr)

    families: dict[str, str] = {}
    fams_file = args.grade_dir / "families.json"
    if fams_file.is_file():
        try:
            families = json.loads(fams_file.read_text())
        except json.JSONDecodeError:
            print(f"aggregate: WARN — families.json is not valid JSON, ignoring", file=sys.stderr)

    canonical: list[dict] = []
    canon_dir = args.grade_dir / "canonical"
    if canon_dir.is_dir():
        for f in sorted(canon_dir.glob("*.json")):
            if f.name in ("baseline.json", "agent-folders.json"):
                continue
            try:
                canonical.append(json.loads(f.read_text()))
            except json.JSONDecodeError as e:
                print(f"aggregate: WARN — {f.name} is not valid JSON: {e}", file=sys.stderr)

    per_agent_dir = args.grade_dir / "per-agent"
    per_agent_dir.mkdir(exist_ok=True)
    for card in cards:
        agent_id = card.get("agent_id", "unknown")
        (per_agent_dir / f"{agent_id}.md").write_text(render_per_agent_md(card))
        (per_agent_dir / f"{agent_id}.json").write_text(json.dumps(card, indent=2))

    cohort_md, cohort_json = render_cohort_md(cards, rubric_yaml, manifest, families, canonical)
    (args.grade_dir / "cohort.md").write_text(cohort_md)
    (args.grade_dir / "cohort.json").write_text(json.dumps(cohort_json, indent=2))

    print(f"per-agent scorecards: {per_agent_dir}/")
    print(f"cohort summary:       {args.grade_dir}/cohort.md")
    print(f"cohort json:          {args.grade_dir}/cohort.json")

    if not args.no_pdf:
        rc = subprocess.call(["python3", str(SKILL_DIR / "report.py"),
                              "--grade-dir", str(args.grade_dir)])
        if rc != 0:
            print(f"aggregate: WARN — report.py failed (exit {rc}); cohort.pdf not generated", file=sys.stderr)


if __name__ == "__main__":
    main()
