#!/usr/bin/env python3
"""Run canonical eval on a cohort of agent submissions — PROGRAMMATIC, no LLM.

Each agent is graded in an isolated subprocess (worker.py) so a crashing or
looping `predict.py` only kills its own worker, never the parent.

Inputs:
    --idea-id idea-01-lateral-attribution
    --agent-folders "module-1/agent-*/final-model" [more globs/paths...]
    --out-dir _grade/<ts>           (default: cwd/_grade/<ts>)
    --concurrency N                 (default: min(N_agents, 8))
    --timeout-per-agent SECONDS     (default: 120)
    --rebuild-baseline              (force V0 recompute)

Outputs (under <out-dir>):
    canonical/<agent_id>.json       — full per-agent scorecard
    canonical/baseline.json         — copy of the cached baseline used this run
    canonical/agent-folders.json    — {agent_id: folder_path, family: ...}
    canonical/run-summary.json      — run metadata (concurrency, wall time, n_ok, n_failed)
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime
import glob
import json
import re
import subprocess
import sys
import time
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILL_DIR))
from baseline import get_baseline  # noqa: E402


def expand_agent_folders(patterns: list[str]) -> list[Path]:
    """Resolve folder globs to concrete agent folders. Each folder is expected to be
    a `final-model/` dir containing manifest.json + predict.py."""
    seen: set[Path] = set()
    out: list[Path] = []
    for pat in patterns:
        matches = [Path(p).resolve() for p in glob.glob(pat)]
        if not matches and "*" not in pat and "?" not in pat:
            print(f"canonical_eval: WARN — no match for {pat}", file=sys.stderr)
        for m in matches:
            if m.is_dir() and m not in seen:
                seen.add(m)
                out.append(m)
    return sorted(out)


def derive_agent_id_and_family(folder: Path) -> tuple[str, str]:
    """Recognise these shapes:
        module-N/agent-MM/final-model           -> ("mN-agent-MM", "module-N")
        modulo-N/agent-MM/final-model           -> ditto
        webinar-angle-X/module-N/agent-MM/...   -> ("angleX-mN-agent-MM", "angle-X/module-N")
        raw-model/idea-NN/agent-MM/...          -> ("raw-agent-MM", "raw")
    """
    parts = folder.parts
    # Find an `agent-NN` ancestor segment.
    agent_idx = None
    for i in range(len(parts) - 1, -1, -1):
        if re.fullmatch(r"agent-(\d+)", parts[i]):
            agent_idx = i
            break
    if agent_idx is None:
        return f"{folder.parent.name}_{folder.name}", "unknown"

    agent_n = re.fullmatch(r"agent-(\d+)", parts[agent_idx]).group(1)
    parent = parts[agent_idx - 1] if agent_idx >= 1 else ""
    grand = parts[agent_idx - 2] if agent_idx >= 2 else ""

    if parent == "raw-model" or grand == "raw-model":
        return f"raw-agent-{agent_n}", "raw"

    m_mod = re.fullmatch(r"(?:module|modulo)-(\d+)", parent)
    m_ang = re.fullmatch(r"webinar-angle-([A-Z0-9]+)", grand)
    if m_mod and m_ang:
        return f"angle{m_ang.group(1)}-m{m_mod.group(1)}-agent-{agent_n}", f"angle-{m_ang.group(1)}/module-{m_mod.group(1)}"
    if m_mod:
        return f"m{m_mod.group(1)}-agent-{agent_n}", f"module-{m_mod.group(1)}"

    return f"{parent}_agent-{agent_n}", parent or "unknown"


def build_platform_lookup(parsed_yaml: dict) -> dict[str, str]:
    """Build {path-substring -> canonical-platform-name} from the YAML's segment_globs.

    The platform name is the path segment immediately following `segments/`,
    e.g. 'sim-only/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv'
         -> {'FORD_F_150_LIGHTNING_MK1': 'FORD_F_150_LIGHTNING_MK1'}

    Derived from the path structure rather than a hardcoded manufacturer
    allowlist so new platforms (HYUNDAI, BYD, …) work without code changes.
    """
    eval_set = parsed_yaml.get("eval_set", {}) or {}
    globs = eval_set.get("segment_globs", []) or []
    lookup: dict[str, str] = {}
    for g in globs:
        m = re.search(r"/segments/([^/]+)/", g)
        if m:
            lookup[m.group(1)] = m.group(1)
    return lookup


def run_one_agent(cfg: dict, *, timeout_s: int) -> dict:
    """Spawn worker.py for one agent. Returns the per-agent scorecard dict."""
    worker = SKILL_DIR / "worker.py"
    started = time.time()
    try:
        proc = subprocess.run(
            ["python3", str(worker)],
            input=json.dumps(cfg),
            capture_output=True, text=True, timeout=timeout_s + 30,
        )
    except subprocess.TimeoutExpired:
        return _failure_record(cfg, "subprocess_timeout", started, stderr_tail="")

    if proc.returncode not in (0, 1) or not proc.stdout.strip():
        return _failure_record(cfg, f"worker_crashed_rc={proc.returncode}", started,
                               stderr_tail=(proc.stderr or "")[-500:])

    try:
        result = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        return _failure_record(cfg, f"worker_bad_json: {e}", started,
                               stderr_tail=(proc.stderr or "")[-500:])

    return result


def _failure_record(cfg: dict, reason: str, started: float, stderr_tail: str) -> dict:
    """Synthesise a per-agent scorecard when the worker itself failed."""
    return {
        "agent_id":     cfg["agent_id"],
        "agent_folder": cfg["agent_folder"],
        "format_checks": {"agent_folder_exists": Path(cfg["agent_folder"]).is_dir()},
        "manifest":     None,
        "execution": {
            "status":               "failed",
            "reason":               reason,
            "n_segments_attempted": 0,
            "n_segments_succeeded": 0,
            "n_segments_skipped_unsupported_platform": 0,
            "n_segments_runtime_error": 0,
            "first_runtime_error":  None,
            "wall_time_seconds":    round(time.time() - started, 2),
            "stderr_tail":          stderr_tail,
        },
        "yaw_rate":     None,
        "cte":          None,
        "per_platform": {},
        "per_segment":  [],
        "coefficients": None,
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--idea-id", required=True)
    p.add_argument("--agent-folders", required=True, nargs="+",
                   help="globs/paths to each agent's final-model folder")
    p.add_argument("--out-dir", type=Path, default=None)
    p.add_argument("--concurrency", type=int, default=0,
                   help="parallel workers (default: min(N, 8))")
    p.add_argument("--timeout-per-agent", type=int, default=120,
                   help="seconds before a single agent's worker is killed (default 120)")
    p.add_argument("--rebuild-baseline", action="store_true")
    args = p.parse_args()

    # Resolve out-dir.
    if args.out_dir is None:
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        args.out_dir = Path.cwd() / "_grade" / ts
    canon = args.out_dir / "canonical"
    canon.mkdir(parents=True, exist_ok=True)

    # Load baseline (cached or compute).
    from baseline import load_canonical_yaml  # noqa: E402
    _, parsed = load_canonical_yaml(args.idea_id)
    baseline = get_baseline(args.idea_id, rebuild=args.rebuild_baseline)
    (canon / "baseline.json").write_text(json.dumps({k: v for k, v in baseline.items() if k != "segment_paths"}, indent=2))

    # Discover agents.
    folders = expand_agent_folders(args.agent_folders)
    if not folders:
        sys.exit("canonical_eval: no agent folders matched")
    agent_records: dict[str, dict] = {}
    cfgs: list[dict] = []
    eval_set = parsed.get("eval_set", {}) or {}
    cte_cfg = parsed.get("cte_metric", {}) or {}
    platform_lookup = build_platform_lookup(parsed)
    for folder in folders:
        agent_id, family = derive_agent_id_and_family(folder)
        agent_records[agent_id] = {"folder": str(folder), "family": family}
        cfgs.append({
            "agent_id":      agent_id,
            "agent_folder":  str(folder),
            "skill_dir":     str(SKILL_DIR),
            "baseline":      baseline,
            "platform_lookup": platform_lookup,
            "sample_filter": eval_set.get("sample_filter", "True"),
            "truth_channel": eval_set.get("truth_channel", "yaw_rate_meas_rads"),
            "input_dir_name": eval_set.get("input_dir_name", "sim/segments"),
            "truth_dir_name": eval_set.get("truth_dir_name", "sim/segments"),
            "grid_step_m":   float(cte_cfg.get("grid_step_m", 1.0)),
            "min_segment_distance_m": float(cte_cfg.get("min_segment_distance_m", 20.0)),
            "timeout_s":     args.timeout_per_agent,
        })
    (canon / "agent-folders.json").write_text(json.dumps(agent_records, indent=2, sort_keys=True))

    print(f"canonical_eval: {len(cfgs)} agents -> {canon}")
    print(f"canonical_eval: V0 baseline yaw={baseline['yaw_rate']['rmse_rad_per_s']:.6f} rad/s, "
          f"CTE={baseline['cte']['rmse_meters']:.4f} m")

    conc = args.concurrency or min(len(cfgs), 8)
    started = time.time()
    n_ok = n_failed = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=conc) as pool:
        future_to_id = {pool.submit(run_one_agent, cfg, timeout_s=args.timeout_per_agent): cfg["agent_id"]
                        for cfg in cfgs}
        for fut in concurrent.futures.as_completed(future_to_id):
            agent_id = future_to_id[fut]
            try:
                result = fut.result()
            except Exception as e:
                result = _failure_record({"agent_id": agent_id, "agent_folder": agent_records[agent_id]["folder"]},
                                         f"future_exception: {e!r}", started, stderr_tail="")
            # Trim the giant per-segment list when writing to disk? No — useful for boxplots.
            (canon / f"{agent_id}.json").write_text(json.dumps(result, indent=2, default=str))
            status = result["execution"]["status"]
            if status == "ok":
                n_ok += 1
                yi = (result.get("yaw_rate") or {}).get("improvement_pct")
                ci = (result.get("cte") or {}).get("improvement_pct")
                print(f"  [ok]     {agent_id:24s}  yaw {yi:+5.1f}%   CTE {ci:+5.1f}%   "
                      f"({result['execution']['wall_time_seconds']:.1f}s)")
            else:
                n_failed += 1
                reason = result["execution"]["reason"] or "unknown"
                print(f"  [FAILED] {agent_id:24s}  {reason}")

    wall = time.time() - started
    summary = {
        "idea_id":               args.idea_id,
        "started_at":            datetime.datetime.fromtimestamp(started).isoformat(timespec="seconds"),
        "wall_time_seconds":     round(wall, 2),
        "n_agents_total":        len(cfgs),
        "n_ok":                  n_ok,
        "n_failed":              n_failed,
        "concurrency":           conc,
        "baseline_cache_key":    baseline.get("cache_key"),
    }
    (canon / "run-summary.json").write_text(json.dumps(summary, indent=2))
    print(f"canonical_eval: done in {wall:.1f}s — {n_ok} ok, {n_failed} failed -> {canon}")


if __name__ == "__main__":
    main()
