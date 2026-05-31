#!/usr/bin/env python3
"""Compute (and cache) V0 baselines for a canonical-eval idea.

The baseline depends only on the val-data pool + the metric definition declared
in `<idea>.canonical.yaml`. It does NOT depend on any agent's submission, so it
is cached at the skill level under `baselines/<idea-id>.baseline.json` and reused
across cohort runs. Recomputed only when the cache hash changes (different val
pool, different segment globs, different filter, etc.) or `--rebuild` is passed.

CLI:
    python3 baseline.py --idea-id idea-01-lateral-attribution
    python3 baseline.py --idea-id idea-01-lateral-attribution --rebuild
    python3 baseline.py --idea-id idea-01-lateral-attribution --print

Importable:
    from baseline import get_baseline
    bl = get_baseline("idea-01-lateral-attribution")
"""

from __future__ import annotations

import argparse
import csv
import datetime
import glob
import hashlib
import json
import math
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SKILL_DIR = Path(__file__).resolve().parent
CHALLENGES_DIR = REPO_ROOT / "webinar-meta" / "domain-knowledge-challenges"
CACHE_DIR = SKILL_DIR / "baselines"
CACHE_DIR.mkdir(exist_ok=True)


def _parse_yaml_minimal(text: str) -> dict:
    """Tiny YAML parser — flat keys, single-level nesting, and `- item` lists.
    Avoids a PyYAML dependency so the skill stays std-lib only."""
    out: dict = {}
    lines = text.splitlines()

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
                j += 1
                continue
            if ":" not in stripped:
                j += 1
                continue
            k, _, v = stripped.partition(":")
            k = k.strip()
            v = v.strip()
            if not v:
                if j + 1 < len(lines):
                    nxt = lines[j + 1]
                    nxt_indent = len(nxt) - len(nxt.lstrip())
                    if nxt.strip().startswith("- ") and nxt_indent > cur_indent:
                        items, j = parse_list(cur_indent + 2, j + 1)
                        block[k] = items
                        continue
                    if nxt_indent > cur_indent:
                        sub, j = parse_block(cur_indent + 2, j + 1)
                        block[k] = sub
                        continue
                block[k] = ""
                j += 1
            else:
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                block[k] = v
                j += 1
        return block, j

    def parse_list(indent: int, start: int) -> tuple[list, int]:
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


def load_canonical_yaml(idea_id: str) -> tuple[str, dict]:
    """Read frontmatter from <idea>.canonical.yaml. Returns (raw_text, parsed)."""
    path = CHALLENGES_DIR / f"{idea_id}.canonical.yaml"
    if not path.is_file():
        sys.exit(f"baseline: missing {path}")
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        sys.exit(f"baseline: {path} has no YAML frontmatter")
    raw = m.group(1)
    parsed = _parse_yaml_minimal(raw)
    return raw, parsed


def cache_key(parsed: dict) -> str:
    """Hash the inputs that affect the baseline. If any change, recompute."""
    eval_set = parsed.get("eval_set", {}) or {}
    cte_cfg = parsed.get("cte_metric", {}) or {}
    inputs = {
        "eval_data_root": parsed.get("eval_data_root", "").strip(),
        "segment_globs": sorted(eval_set.get("segment_globs", []) or []),
        "sample_filter": eval_set.get("sample_filter", "True"),
        "truth_channel": eval_set.get("truth_channel", "yaw_rate_meas_rads"),
        "grid_step_m": float(cte_cfg.get("grid_step_m", 1.0)),
        "min_segment_distance_m": float(cte_cfg.get("min_segment_distance_m", 20.0)),
    }
    blob = json.dumps(inputs, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def compute_baseline(parsed: dict) -> dict:
    """Stream the val pool, compute both V0 RMSEs. Pure function of inputs."""
    eval_set = parsed.get("eval_set", {}) or {}
    globs = eval_set.get("segment_globs", []) or []
    if not globs:
        sys.exit("baseline: eval_set.segment_globs missing")
    sample_filter_expr = eval_set.get("sample_filter", "True")
    truth_col = eval_set.get("truth_channel", "yaw_rate_meas_rads")
    eval_root_str = parsed.get("eval_data_root", "").strip()
    eval_root = Path(eval_root_str) if eval_root_str else REPO_ROOT
    if not eval_root.is_dir():
        sys.exit(f"baseline: eval_data_root does not exist: {eval_root}")

    seg_paths: list[Path] = []
    for g in globs:
        for p in glob.glob(str(eval_root / g), recursive=True):
            seg_paths.append(Path(p))
    seg_paths = sorted(set(seg_paths))
    if not seg_paths:
        sys.exit(f"baseline: no segments matched globs under {eval_root}")

    # KPI 1: pooled yaw-rate RMSE.
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
        sys.exit("baseline: zero yaw-rate samples after filter")
    yaw_rmse = math.sqrt(sum_sq / n)

    # KPI 2: distance-resampled CTE RMSE.
    cte_cfg = parsed.get("cte_metric", {}) or {}
    grid_step_m = float(cte_cfg.get("grid_step_m", 1.0))
    min_dist_m = float(cte_cfg.get("min_segment_distance_m", 20.0))

    sys.path.insert(0, str(SKILL_DIR))
    from traj_metrics import cte_baseline_from_segments  # noqa: E402

    cte = cte_baseline_from_segments(
        segment_paths=seg_paths,
        truth_channel=truth_col,
        pred_channel="yaw_rate_pred_rads",
        grid_step_m=grid_step_m,
        min_distance_m=min_dist_m,
        sample_filter_expr=sample_filter_expr,
    )

    return {
        "yaw_rate": {
            "rmse_rad_per_s": yaw_rmse,
            "n_samples_after_filter": n,
            "truth_channel": truth_col,
            "sample_filter": sample_filter_expr,
        },
        "cte": cte,
        "n_segments": len(seg_paths),
        "segment_paths": [str(p) for p in seg_paths],
        "eval_data_root": str(eval_root),
        "globs": globs,
    }


def cache_path(idea_id: str) -> Path:
    return CACHE_DIR / f"{idea_id}.baseline.json"


def get_baseline(idea_id: str, *, rebuild: bool = False, quiet: bool = False) -> dict:
    """Return the V0 baseline for an idea. Uses cache if hash matches; else recomputes."""
    raw, parsed = load_canonical_yaml(idea_id)
    key = cache_key(parsed)
    cp = cache_path(idea_id)
    if cp.is_file() and not rebuild:
        try:
            cached = json.loads(cp.read_text())
            if cached.get("cache_key") == key:
                if not quiet:
                    print(f"baseline: cache hit {cp.name} (key={key})")
                return cached
            if not quiet:
                print(f"baseline: cache stale (key {cached.get('cache_key')} -> {key}); recomputing")
        except json.JSONDecodeError:
            if not quiet:
                print(f"baseline: cache unreadable; recomputing")

    if not quiet:
        print(f"baseline: computing V0 from eval pool...")
    bl = compute_baseline(parsed)
    bl["cache_key"] = key
    bl["computed_at"] = datetime.datetime.now().isoformat(timespec="seconds")
    bl["idea_id"] = idea_id
    cp.write_text(json.dumps(bl, indent=2))
    if not quiet:
        print(f"  yaw V0 RMSE  = {bl['yaw_rate']['rmse_rad_per_s']:.6f} rad/s "
              f"({bl['yaw_rate']['n_samples_after_filter']:,} samples)")
        print(f"  CTE V0 RMSE  = {bl['cte']['rmse_meters']:.4f} m "
              f"({bl['cte']['n_distance_bins']:,} bins, {bl['cte']['n_segments_used']} segments)")
        print(f"  cached -> {cp}")
    return bl


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--idea-id", required=True)
    p.add_argument("--rebuild", action="store_true", help="force recompute even if cache is fresh")
    p.add_argument("--print", action="store_true", help="print the cached baseline and exit")
    args = p.parse_args()

    bl = get_baseline(args.idea_id, rebuild=args.rebuild)
    if args.print:
        print(json.dumps({k: v for k, v in bl.items() if k != "segment_paths"}, indent=2))


if __name__ == "__main__":
    main()
