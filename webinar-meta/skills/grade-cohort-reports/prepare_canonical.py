#!/usr/bin/env python3
"""Prepare canonical-eval grading: precompute V0 baseline, render per-agent prompts.

Usage:
    python3 prepare_canonical.py \\
        --idea-id idea-01-lateral-attribution \\
        --reports "<glob>" [more globs or paths...] \\
        [--out-dir /abs/path/to/_grade/<timestamp>]

What it produces (under <out-dir>):
    canonical/baseline.json              # precomputed V0 RMSE on canonical eval set
    canonical/agent-folders.json         # {agent_id: agent_folder_path}
    canonical-judge-<agent_id>.prompt.md # one per agent
    canonical-invocations.json           # Agent() calls for the parent to fire
    canonical-eval-snapshot.yaml         # the eval spec at grading time

Does NOT call the Agent tool itself — emits the JSON the parent assistant should fire.
"""

import argparse
import datetime
import glob
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
# Challenges live under webinar-meta (relocated from webinar-00 in May 2026).
CHALLENGES_DIR = REPO_ROOT / "webinar-meta" / "domain-knowledge-challenges"
SKILL_DIR = Path(__file__).resolve().parent

# Reuse derive_agent_id_and_family from prepare.py.
sys.path.insert(0, str(SKILL_DIR))
from prepare import derive_agent_id_and_family, expand_reports  # noqa: E402


def load_canonical_yaml(idea_id: str) -> tuple[str, dict]:
    """Read the YAML frontmatter from idea-NN-*.canonical.yaml. Returns (raw_text, parsed_dict)."""
    path = CHALLENGES_DIR / f"{idea_id}.canonical.yaml"
    if not path.is_file():
        sys.exit(f"prepare_canonical: missing {path}")
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        sys.exit(f"prepare_canonical: {path} has no YAML frontmatter")
    raw = m.group(1)
    # Minimal parse — only need eval_set.segment_globs and sample_filter and truth_channel for the baseline calc.
    parsed = _parse_yaml_minimal(raw)
    return raw, parsed


def _parse_yaml_minimal(text: str) -> dict:
    """Very small YAML parser — handles our flat fields, lists, and simple nesting only.
    Avoids pulling PyYAML. Recognises:
      - top-level key: value
      - top-level key:\n  subkey: value
      - lists with `- item`
    """
    out: dict = {}
    lines = text.splitlines()
    i = 0

    def parse_block(indent: int, start: int) -> tuple[dict, int]:
        block: dict = {}
        j = start
        while j < len(lines):
            raw = lines[j]
            if not raw.strip() or raw.lstrip().startswith("#"):
                j += 1
                continue
            cur_indent = len(raw) - len(raw.lstrip())
            if cur_indent < indent:
                return block, j
            if cur_indent > indent:
                j += 1
                continue
            stripped = raw.strip()
            if stripped.startswith("- "):
                # We don't expect lists at this level for our schema.
                j += 1
                continue
            if ":" in stripped:
                k, _, v = stripped.partition(":")
                k = k.strip()
                v = v.strip()
                if not v:
                    # Could be a sublist or a sub-block.
                    # Peek next line.
                    if j + 1 < len(lines):
                        nxt = lines[j + 1]
                        nxt_indent = len(nxt) - len(nxt.lstrip())
                        if nxt.strip().startswith("- ") and nxt_indent > cur_indent:
                            items, j = _parse_list(cur_indent + 2, j + 1)
                            block[k] = items
                            continue
                        if nxt_indent > cur_indent:
                            sub, j = parse_block(cur_indent + 2, j + 1)
                            block[k] = sub
                            continue
                    block[k] = ""
                    j += 1
                else:
                    # Strip wrapping quotes.
                    if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                        v = v[1:-1]
                    block[k] = v
                    j += 1
            else:
                j += 1
        return block, j

    def _parse_list(indent: int, start: int) -> tuple[list, int]:
        items: list = []
        j = start
        while j < len(lines):
            raw = lines[j]
            if not raw.strip():
                j += 1
                continue
            cur_indent = len(raw) - len(raw.lstrip())
            stripped = raw.strip()
            if not stripped.startswith("-") or cur_indent < indent:
                return items, j
            items.append(stripped[1:].strip())
            j += 1
        return items, j

    out, _ = parse_block(0, 0)
    return out


def compute_baseline(parsed_yaml: dict) -> dict:
    """Compute V0 baselines across the canonical eval set for BOTH primary KPIs:

    - yaw_rate_rmse: pooled-sample yaw-rate RMSE in rad/s
    - cte_rmse:      distance-resampled cross-track-error RMSE in meters

    Returns a single dict ready to serialize as baseline.json. The structure is
    nested under "yaw_rate" and "cte" keys; legacy `rmse_rad_per_s` is mirrored
    at the top level so older readers don't break.
    """
    import csv
    import math

    eval_set = parsed_yaml.get("eval_set", {})
    globs = eval_set.get("segment_globs", [])
    if not globs:
        sys.exit("prepare_canonical: eval_set.segment_globs missing in YAML")
    sample_filter_expr = eval_set.get("sample_filter", "True")
    truth_col = eval_set.get("truth_channel", "yaw_rate_meas_rads")

    # If the YAML declares an eval_data_root, resolve globs against that. Otherwise
    # fall back to REPO_ROOT (legacy behaviour, when train and eval shared the repo).
    eval_root_str = parsed_yaml.get("eval_data_root", "").strip()
    eval_root = Path(eval_root_str) if eval_root_str else REPO_ROOT
    if not eval_root.is_dir():
        sys.exit(f"prepare_canonical: eval_data_root does not exist: {eval_root}")

    seg_paths: list[Path] = []
    for g in globs:
        for p in glob.glob(str(eval_root / g), recursive=True):
            seg_paths.append(Path(p))
    seg_paths = sorted(set(seg_paths))

    print(f"prepare_canonical: eval_data_root = {eval_root}")
    print(f"prepare_canonical: globbed {len(seg_paths)} sim.csv files for V0 baselines")

    # ---- KPI 1: pooled yaw-rate RMSE ----
    sum_sq = 0.0
    n = 0
    fcode = compile(f"({sample_filter_expr})", "<filter>", "eval")
    for p in seg_paths:
        with p.open(newline="") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                try:
                    v_mps = float(row["v_mps"])
                    pred = float(row["yaw_rate_pred_rads"])
                    truth = float(row[truth_col])
                except (KeyError, ValueError):
                    continue
                if not eval(fcode, {"v_mps": v_mps, "math": math}):
                    continue
                d = pred - truth
                sum_sq += d * d
                n += 1
    if n == 0:
        sys.exit("prepare_canonical: zero yaw-rate samples after filter — check segment_globs and sample_filter")
    yaw_rmse = math.sqrt(sum_sq / n)
    print(f"  yaw-rate V0 RMSE = {yaw_rmse:.6f} rad/s over {n:,} samples in {len(seg_paths)} segments")

    # ---- KPI 2: distance-resampled CTE RMSE ----
    # Read cte_rmse config from the YAML's flat `cte_metric:` block (the `metrics:`
    # list is descriptive only — the minimal YAML parser cannot recurse into list items).
    cte_cfg = parsed_yaml.get("cte_metric", {}) or {}
    grid_step_m = float(cte_cfg.get("grid_step_m", 1.0))
    min_dist_m = float(cte_cfg.get("min_segment_distance_m", 20.0))

    sys.path.insert(0, str(SKILL_DIR))
    from traj_metrics import cte_baseline_from_segments  # noqa: E402

    cte_baseline = cte_baseline_from_segments(
        segment_paths=seg_paths,
        truth_channel=truth_col,
        pred_channel="yaw_rate_pred_rads",
        grid_step_m=grid_step_m,
        min_distance_m=min_dist_m,
        sample_filter_expr=sample_filter_expr,
    )
    print(f"  CTE V0 RMSE = {cte_baseline['rmse_meters']:.4f} m over "
          f"{cte_baseline['n_distance_bins']:,} distance-bins in "
          f"{cte_baseline['n_segments_used']} segments "
          f"({cte_baseline['n_segments_skipped_short']} short, "
          f"{cte_baseline['n_segments_skipped_bad']} bad)")

    return {
        # Nested per-metric blocks — the new contract.
        "yaw_rate": {
            "rmse_rad_per_s": yaw_rmse,
            "n_samples_after_filter": n,
            "truth_channel": truth_col,
            "sample_filter": sample_filter_expr,
        },
        "cte": cte_baseline,
        # Common metadata.
        "n_segments": len(seg_paths),
        "eval_data_root": str(eval_root),
        "globs": globs,
        "computed_at": datetime.datetime.now().isoformat(timespec="seconds"),
        # Legacy top-level mirror — old readers and the existing aggregate.py
        # field name continue to work.
        "rmse_rad_per_s": yaw_rmse,
        "n_samples_after_filter": n,
        "truth_channel": truth_col,
        "sample_filter": sample_filter_expr,
    }




def main():
    p = argparse.ArgumentParser()
    p.add_argument("--idea-id", required=True)
    p.add_argument("--reports", required=True, nargs="+")
    p.add_argument("--out-dir", type=Path, default=None)
    args = p.parse_args()

    eval_yaml_raw, eval_yaml_parsed = load_canonical_yaml(args.idea_id)
    reports = expand_reports(args.reports)

    if args.out_dir is None:
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        args.out_dir = Path.cwd() / "_grade" / ts
    args.out_dir.mkdir(parents=True, exist_ok=True)
    canon_dir = args.out_dir / "canonical"
    canon_dir.mkdir(exist_ok=True)

    # Snapshot the eval spec for reproducibility.
    (args.out_dir / "canonical-eval-snapshot.yaml").write_text(eval_yaml_raw)

    # 1) Compute V0 baseline (once).
    print("prepare_canonical: computing V0 baselines (yaw-rate + CTE) across canonical eval set...")
    baseline = compute_baseline(eval_yaml_parsed)
    (canon_dir / "baseline.json").write_text(json.dumps(baseline, indent=2))
    print(f"  baseline.json written to {canon_dir}")

    # 2) Render one canonical-eval prompt per agent.
    template = (SKILL_DIR / "canonical-eval-template.md").read_text()
    parts = template.split("---", 2)
    body = parts[2] if len(parts) >= 3 else template

    agent_folders: dict[str, str] = {}
    invocations: list[dict] = []
    for report in reports:
        agent_id, family = derive_agent_id_and_family(report)
        agent_folder = report.parent
        agent_folders[agent_id] = str(agent_folder)
        output_path = canon_dir / f"{agent_id}.json"
        prompt = (body
                  .replace("{{agent_id}}", agent_id)
                  .replace("{{agent_folder}}", str(agent_folder))
                  .replace("{{report_path}}", str(report))
                  .replace("{{eval_yaml}}", eval_yaml_raw)
                  .replace("{{baseline_json}}", json.dumps(baseline, indent=2))
                  .replace("{{skill_dir}}", str(SKILL_DIR))
                  .replace("{{output_path}}", str(output_path)))
        prompt_file = args.out_dir / f"canonical-judge-{agent_id}.prompt.md"
        prompt_file.write_text(prompt)
        invocations.append({
            "subagent_type": "general-purpose",
            "description": f"canonical-eval {agent_id}",
            "run_in_background": True,
            "agent_id": agent_id,
            "family": family,
            "report_path": str(report),
            "agent_folder": str(agent_folder),
            "output_path": str(output_path),
            "prompt": prompt,
        })

    (canon_dir / "agent-folders.json").write_text(json.dumps(agent_folders, indent=2, sort_keys=True))
    (args.out_dir / "canonical-invocations.json").write_text(json.dumps(invocations, indent=2))

    print(f"out_dir: {args.out_dir}")
    print(f"reports: {len(reports)}")
    print()
    payload = [{"subagent_type": inv["subagent_type"],
                "description": inv["description"],
                "run_in_background": inv["run_in_background"],
                "agent_id": inv["agent_id"],
                "prompt": inv["prompt"]}
               for inv in invocations]
    print("BEGIN_CANONICAL_INVOCATIONS")
    print(json.dumps(payload))
    print("END_CANONICAL_INVOCATIONS")
    print()
    print(f"Next: fire all {len(payload)} canonical-eval Agent() calls in ONE message (run_in_background=true).")
    print(f"      Each subagent writes its JSON to {canon_dir}/<agent_id>.json directly.")
    print(f"      Then: python3 aggregate.py --grade-dir {args.out_dir}  (canonical section auto-included)")


if __name__ == "__main__":
    main()
