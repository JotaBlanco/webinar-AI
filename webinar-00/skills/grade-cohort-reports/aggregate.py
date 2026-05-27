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
import re
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


def render_cohort_md(cards: list[dict], rubric_yaml: str, manifest: dict) -> tuple[str, dict]:
    out_lines: list[str] = []
    cohort_json: dict = {"n_agents": len(cards), "per_item": {}, "headline": [], "convergence": {}, "honesty": {}}

    out_lines.append(f"# Cohort grading — {len(cards)} agents")
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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--grade-dir", type=Path, required=True)
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

    per_agent_dir = args.grade_dir / "per-agent"
    per_agent_dir.mkdir(exist_ok=True)
    for card in cards:
        agent_id = card.get("agent_id", "unknown")
        (per_agent_dir / f"{agent_id}.md").write_text(render_per_agent_md(card))
        (per_agent_dir / f"{agent_id}.json").write_text(json.dumps(card, indent=2))

    cohort_md, cohort_json = render_cohort_md(cards, rubric_yaml, manifest)
    (args.grade_dir / "cohort.md").write_text(cohort_md)
    (args.grade_dir / "cohort.json").write_text(json.dumps(cohort_json, indent=2))

    print(f"per-agent scorecards: {per_agent_dir}/")
    print(f"cohort summary:       {args.grade_dir}/cohort.md")
    print(f"cohort json:          {args.grade_dir}/cohort.json")


if __name__ == "__main__":
    main()
