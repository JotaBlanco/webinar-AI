#!/usr/bin/env python3
"""Aggregate per-agent canonical scorecards into a single cohort.json.

Reads:
    <grade-dir>/canonical/<agent_id>.json       (one per agent)
    <grade-dir>/canonical/baseline.json
    <grade-dir>/canonical/agent-folders.json
    <grade-dir>/canonical/run-summary.json
    <grade-dir>/self-reported/<agent_id>.json   (optional, --with-self-reported)

Writes:
    <grade-dir>/cohort.json                     — everything needed by report.py

The aggregator does NOT render Markdown / HTML / PDF — that's report.py's job.
Its sole purpose is to compute every statistic the renderers might want, in one
place, so the renderers stay dumb (purely format) and consistent across formats.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path


def _safe_stats(values: list[float]) -> dict:
    clean = [v for v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not clean:
        return {"n": 0, "mean": None, "median": None, "std": None, "min": None, "max": None}
    return {
        "n":      len(clean),
        "mean":   round(statistics.fmean(clean), 4),
        "median": round(statistics.median(clean), 4),
        "std":    round(statistics.pstdev(clean), 4) if len(clean) >= 2 else 0.0,
        "min":    round(min(clean), 4),
        "max":    round(max(clean), 4),
    }


def load_canonical(grade_dir: Path) -> tuple[list[dict], dict, dict, dict]:
    """Return (cards, baseline, agent_folders, run_summary)."""
    canon = grade_dir / "canonical"
    if not canon.is_dir():
        sys.exit(f"aggregate: missing {canon}")
    baseline = json.loads((canon / "baseline.json").read_text())
    agent_folders = json.loads((canon / "agent-folders.json").read_text()) if (canon / "agent-folders.json").is_file() else {}
    run_summary = json.loads((canon / "run-summary.json").read_text()) if (canon / "run-summary.json").is_file() else {}
    cards = []
    for f in sorted(canon.glob("*.json")):
        if f.name in ("baseline.json", "agent-folders.json", "run-summary.json"):
            continue
        try:
            cards.append(json.loads(f.read_text()))
        except json.JSONDecodeError as e:
            print(f"aggregate: WARN — {f.name} is not valid JSON: {e}", file=sys.stderr)
    return cards, baseline, agent_folders, run_summary


def load_self_reported(grade_dir: Path) -> dict[str, dict]:
    """Optional: {agent_id: {claimed_yaw_improvement_pct, claimed_cte_improvement_pct, ...}}."""
    sd = grade_dir / "self-reported"
    if not sd.is_dir():
        return {}
    out: dict[str, dict] = {}
    for f in sorted(sd.glob("*.json")):
        if f.name in ("invocations.json",):
            continue
        try:
            data = json.loads(f.read_text())
            aid = data.get("agent_id")
            if aid:
                out[aid] = data
        except json.JSONDecodeError as e:
            print(f"aggregate: WARN — self-reported/{f.name} bad JSON: {e}", file=sys.stderr)
    return out


def winners(cards_ok: list[dict]) -> dict:
    """Best/worst on each KPI; agents winning both above a threshold."""
    def by(metric_path: tuple[str, str]) -> list[tuple[str, float]]:
        out: list[tuple[str, float]] = []
        for c in cards_ok:
            v = c.get(metric_path[0])
            if v is None:
                continue
            x = v.get(metric_path[1])
            if x is not None:
                out.append((c["agent_id"], x))
        return sorted(out, key=lambda kv: kv[1], reverse=True)

    yaw_sorted = by(("yaw_rate", "improvement_pct"))
    cte_sorted = by(("cte", "improvement_pct"))

    def double_winners(threshold: float) -> list[str]:
        ok_ids = set(a for a, v in yaw_sorted if v >= threshold) & set(a for a, v in cte_sorted if v >= threshold)
        return [a for a, _ in yaw_sorted if a in ok_ids]

    return {
        "yaw_top3":   yaw_sorted[:3],
        "yaw_bot3":   list(reversed(yaw_sorted[-3:])) if len(yaw_sorted) >= 3 else list(reversed(yaw_sorted)),
        "cte_top3":   cte_sorted[:3],
        "cte_bot3":   list(reversed(cte_sorted[-3:])) if len(cte_sorted) >= 3 else list(reversed(cte_sorted)),
        "double_25":  double_winners(25.0),
        "double_30":  double_winners(30.0),
    }


def per_family(cards_ok: list[dict], cards_all: list[dict], families: dict[str, str]) -> dict:
    """Group by family (module-1, module-2, etc). For each, report stats on both KPIs +
    number that survived reconstruction."""
    by_fam_ok: dict[str, list[dict]] = defaultdict(list)
    by_fam_all: dict[str, list[dict]] = defaultdict(list)
    for c in cards_all:
        by_fam_all[families.get(c["agent_id"], "unknown")].append(c)
    for c in cards_ok:
        by_fam_ok[families.get(c["agent_id"], "unknown")].append(c)

    fam_order = sorted(by_fam_all.keys(), key=lambda f: (f != "raw", f))
    out = {}
    for fam in fam_order:
        ok = by_fam_ok.get(fam, [])
        all_ = by_fam_all[fam]
        yaw = [(c.get("yaw_rate") or {}).get("improvement_pct") for c in ok]
        cte = [(c.get("cte") or {}).get("improvement_pct") for c in ok]
        out[fam] = {
            "n_total":  len(all_),
            "n_ok":     len(ok),
            "n_failed": len(all_) - len(ok),
            "yaw_pct":  _safe_stats(yaw),
            "cte_pct":  _safe_stats(cte),
            "agent_ids": [c["agent_id"] for c in all_],
        }
    return out, fam_order


def per_platform_pivot(cards_ok: list[dict]) -> dict:
    """Per-platform: how many agents support it, mean/std improvement on each KPI."""
    by_plat: dict[str, dict] = defaultdict(lambda: {"yaw": [], "cte": [], "agents": []})
    for c in cards_ok:
        for plat, pp in (c.get("per_platform") or {}).items():
            baseline_yaw = (c.get("yaw_rate") or {}).get("baseline_rmse")
            baseline_cte = (c.get("cte") or {}).get("baseline_rmse_meters")
            plat_yaw = (pp.get("yaw_rate") or {}).get("agent_rmse")
            plat_cte = (pp.get("cte") or {}).get("agent_rmse_meters")
            if baseline_yaw and plat_yaw is not None:
                by_plat[plat]["yaw"].append((baseline_yaw - plat_yaw) / baseline_yaw * 100)
            if baseline_cte and plat_cte is not None:
                by_plat[plat]["cte"].append((baseline_cte - plat_cte) / baseline_cte * 100)
            if plat_yaw is not None or plat_cte is not None:
                by_plat[plat]["agents"].append(c["agent_id"])
    out = {}
    for plat, blk in by_plat.items():
        out[plat] = {
            "n_agents":   len(blk["agents"]),
            "yaw_pct":    _safe_stats(blk["yaw"]),
            "cte_pct":    _safe_stats(blk["cte"]),
        }
    return out


def per_agent_platform_breakdown(cards_ok: list[dict], baseline: dict) -> dict:
    """For each (agent, platform), surface yaw + CTE Δ% so the faceted scatter can plot them."""
    bl_yaw = baseline["yaw_rate"]["rmse_rad_per_s"]
    bl_cte = baseline["cte"]["rmse_meters"]
    out: dict[str, dict] = {}
    for c in cards_ok:
        agent_block: dict[str, dict] = {}
        for plat, pp in (c.get("per_platform") or {}).items():
            plat_yaw = (pp.get("yaw_rate") or {}).get("agent_rmse")
            plat_cte = (pp.get("cte") or {}).get("agent_rmse_meters")
            agent_block[plat] = {
                "yaw_agent_rmse":           plat_yaw,
                "yaw_improvement_pct":      ((bl_yaw - plat_yaw) / bl_yaw * 100) if plat_yaw is not None else None,
                "cte_agent_rmse_meters":    plat_cte,
                "cte_improvement_pct":      ((bl_cte - plat_cte) / bl_cte * 100) if plat_cte is not None else None,
                "n_segments_ok":            pp.get("n_segments_ok"),
            }
        out[c["agent_id"]] = agent_block
    return out


def per_segment_distribution(cards_ok: list[dict]) -> dict:
    """For each agent, summary stats of per-segment yaw RMSE & CTE — for the boxplot."""
    out: dict[str, dict] = {}
    for c in cards_ok:
        yaws = [s["yaw_rmse"] for s in (c.get("per_segment") or []) if s.get("yaw_rmse") is not None]
        ctes = [s["cte_rmse_m"] for s in (c.get("per_segment") or []) if s.get("cte_rmse_m") is not None]
        out[c["agent_id"]] = {
            "yaw_segment_rmse": _safe_stats(yaws),
            "cte_segment_rmse": _safe_stats(ctes),
            "yaw_segment_values": yaws,
            "cte_segment_values": ctes,
        }
    return out


def leak_audit(cards_all: list[dict]) -> dict:
    """Surface contract-enforcement signals: which agents referenced truth columns
    in their predict() body (or in a helper function called from predict).
    Doesn't affect scoring (the allowlist makes the leak inert), but a key
    audit/diagnostic signal."""
    per_agent: dict[str, dict] = {}
    n_attempted = 0
    n_via_helper = 0
    columns_attempted = Counter()
    for c in cards_all:
        scan = ((c.get("contract") or {}).get("leak_scan") or {})
        body_hits = scan.get("hits_in_predict_body") or {}
        helper_hits = scan.get("hits_in_helpers") or {}
        rest_hits = scan.get("hits_elsewhere") or {}
        merged = set(body_hits) | set(helper_hits)
        if merged:
            n_attempted += 1
            if not body_hits:
                n_via_helper += 1
            for col in merged:
                columns_attempted[col] += 1
        per_agent[c["agent_id"]] = {
            "scan_ok":              scan.get("scan_ok", False),
            "hits_in_predict_body": body_hits,
            "hits_in_helpers":      helper_hits,
            "hits_elsewhere":       rest_hits,
            "stripped_columns_per_segment": (c.get("contract") or {}).get("stripped_columns_per_segment"),
        }
    return {
        "n_agents_attempted_leak":           n_attempted,
        "n_agents_leak_via_helper_only":     n_via_helper,
        "columns_attempted_count":           dict(columns_attempted),
        "per_agent":                         per_agent,
    }


def reconstruction_quality(cards_all: list[dict]) -> dict:
    """Tally format check results across the cohort — substrate signal."""
    counters: dict[str, Counter] = defaultdict(Counter)
    failure_reasons = Counter()
    n = len(cards_all)
    for c in cards_all:
        for k, v in (c.get("format_checks") or {}).items():
            counters[k][bool(v)] += 1
        if c["execution"]["status"] != "ok":
            failure_reasons[c["execution"]["reason"] or "unknown"] += 1
    return {
        "n_agents":           n,
        "format_check_pass":  {k: c[True] for k, c in counters.items()},
        "format_check_fail":  {k: c[False] for k, c in counters.items()},
        "failure_reasons":    dict(failure_reasons),
    }


def coefficient_summary(cards_ok: list[dict]) -> dict:
    """For each agent, expose a flattened coefficient view — the calibration card."""
    out: dict[str, dict] = {}
    for c in cards_ok:
        coeffs = c.get("coefficients")
        if coeffs is None:
            continue
        out[c["agent_id"]] = coeffs
    return out


def _leak_attempt_for(card: dict) -> dict:
    scan = ((card.get("contract") or {}).get("leak_scan") or {})
    body = scan.get("hits_in_predict_body") or {}
    helpers = scan.get("hits_in_helpers") or {}
    merged = {**body, **{k: helpers[k] + body.get(k, 0) for k in helpers}}
    return {
        "attempted_leak":          bool(merged),
        "leak_columns":            sorted(merged.keys()),
        "leak_via_helper":         bool(helpers and not body),
    }


def per_agent_table(cards_all: list[dict], families: dict[str, str], self_reported: dict[str, dict]) -> list[dict]:
    """Wide per-agent row used by the renderer."""
    rows = []
    for c in cards_all:
        aid = c["agent_id"]
        fam = families.get(aid, "unknown")
        st = c["execution"]["status"]
        yaw = c.get("yaw_rate") or {}
        cte = c.get("cte") or {}
        exec_ = c["execution"]
        row = {
            "agent_id":           aid,
            "family":             fam,
            "status":             st,
            "reason":             exec_.get("reason"),
            "yaw_baseline_rmse":  yaw.get("baseline_rmse"),
            "yaw_agent_rmse":     yaw.get("agent_rmse"),
            "yaw_pct":            yaw.get("improvement_pct"),
            "cte_baseline_m":     cte.get("baseline_rmse_meters"),
            "cte_agent_m":        cte.get("agent_rmse_meters"),
            "cte_pct":            cte.get("improvement_pct"),
            "n_seg_ok":           exec_.get("n_segments_succeeded"),
            "n_seg_total":        exec_.get("n_segments_attempted"),
            "wall_seconds":       exec_.get("wall_time_seconds"),
            "platforms_supported": (c.get("manifest") or {}).get("platform_support", []) if c.get("manifest") else [],
            **_leak_attempt_for(c),
        }
        sr = self_reported.get(aid)
        if sr:
            row["claimed_yaw_pct"] = sr.get("claimed_yaw_pct")
            row["claimed_cte_pct"] = sr.get("claimed_cte_pct")
            row["yaw_gap"] = (
                (sr["claimed_yaw_pct"] - row["yaw_pct"])
                if sr.get("claimed_yaw_pct") is not None and row["yaw_pct"] is not None else None
            )
            row["cte_gap"] = (
                (sr["claimed_cte_pct"] - row["cte_pct"])
                if sr.get("claimed_cte_pct") is not None and row["cte_pct"] is not None else None
            )
        rows.append(row)
    return rows


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--grade-dir", type=Path, required=True)
    args = p.parse_args()

    cards, baseline, agent_folders, run_summary = load_canonical(args.grade_dir)
    families = {aid: meta.get("family", "unknown") for aid, meta in agent_folders.items()}
    self_reported = load_self_reported(args.grade_dir)

    cards_ok = [c for c in cards if c["execution"]["status"] == "ok"]
    cards_failed = [c for c in cards if c["execution"]["status"] != "ok"]

    fam_section, fam_order = per_family(cards_ok, cards, families)

    cohort = {
        "schema_version":  "2.0",
        "idea_id":         baseline.get("idea_id"),
        "baseline":        {k: v for k, v in baseline.items() if k != "segment_paths"},
        "run":             run_summary,
        "n_agents_total":  len(cards),
        "n_ok":            len(cards_ok),
        "n_failed":        len(cards_failed),
        "families":        fam_section,
        "family_order":    fam_order,
        "winners":         winners(cards_ok),
        "per_platform":    per_platform_pivot(cards_ok),
        "per_agent_platform_breakdown": per_agent_platform_breakdown(cards_ok, baseline),
        "per_segment":     per_segment_distribution(cards_ok),
        "reconstruction":  reconstruction_quality(cards),
        "leak_audit":      leak_audit(cards),
        "coefficients":    coefficient_summary(cards_ok),
        "per_agent":       per_agent_table(cards, families, self_reported),
        "self_reported_loaded": bool(self_reported),
    }
    out = args.grade_dir / "cohort.json"
    out.write_text(json.dumps(cohort, indent=2, default=str))
    print(f"aggregate: cohort.json -> {out}")
    print(f"           {cohort['n_ok']} ok, {cohort['n_failed']} failed across {len(fam_order)} families")


if __name__ == "__main__":
    main()
