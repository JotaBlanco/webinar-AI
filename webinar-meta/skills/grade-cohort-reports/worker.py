#!/usr/bin/env python3
"""Per-agent canonical-eval worker. Runs in a SEPARATE subprocess for isolation.

Reads JSON config from stdin:
    {
      "agent_id": "...",
      "agent_folder": "/abs/path/to/final-model",
      "skill_dir":    "/abs/path/to/skill",
      "baseline":     <the full baseline dict from baseline.json>,
      "platform_lookup": {
          "FORD_F_150_LIGHTNING_MK1": "FORD_F_150_LIGHTNING_MK1",
          ...                      # path-substring -> platform-name mapping
      },
      "sample_filter": "v_mps > 2.0",
      "truth_channel": "yaw_rate_meas_rads",
      "grid_step_m":   1.0,
      "min_segment_distance_m": 20.0
    }

Writes a single JSON object to stdout: the full per-agent canonical scorecard
(see schema in canonical_eval.py docstring).

Exit codes:
    0 — wrote valid JSON to stdout
    1 — wrote a `status="failed"` JSON to stdout (graceful failure)
    2 — crashed before producing JSON (parent will synthesise a failure record)
"""

from __future__ import annotations

import csv
import importlib.util
import io
import json
import math
import os
import re
import sys
import time
import traceback
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path


def derive_platform(seg_path: Path, lookup: dict[str, str]) -> str | None:
    """Find which platform a sim.csv belongs to by looking for a known token in the path."""
    s = str(seg_path)
    for token, name in lookup.items():
        if token in s:
            return name
    return None


def load_predict(agent_folder: Path, manifest: dict):
    """Resolve `predict_callable` (e.g. 'predict.py:predict' or
    'final-model/predict.py:predict') against agent_folder and import it."""
    spec = manifest.get("predict_callable", "predict.py:predict")
    if ":" not in spec:
        raise ValueError(f"manifest.predict_callable must be 'path.py:funcname', got {spec!r}")
    rel, fn_name = spec.rsplit(":", 1)
    # Strip a leading 'final-model/' if the manifest writes it (some agents do).
    rel = re.sub(r"^final-model/", "", rel)
    pred_path = (agent_folder / rel).resolve()
    if not pred_path.is_file():
        raise FileNotFoundError(f"predict file not found: {pred_path}")
    module_name = f"_agent_predict_{abs(hash(str(pred_path)))}"
    pyspec = importlib.util.spec_from_file_location(module_name, pred_path)
    if pyspec is None or pyspec.loader is None:
        raise ImportError(f"could not build spec for {pred_path}")
    mod = importlib.util.module_from_spec(pyspec)
    # Add the folder to sys.path so relative imports / sibling reads (coeffs.json) work.
    sys.path.insert(0, str(pred_path.parent))
    pyspec.loader.exec_module(mod)
    fn = getattr(mod, fn_name, None)
    if fn is None:
        raise AttributeError(f"{pred_path}:{fn_name} not found")
    if not callable(fn):
        raise TypeError(f"{spec} is not callable")
    return fn


def format_checks(agent_folder: Path) -> tuple[dict, dict | None]:
    """Inspect the final-model folder structure. Returns (checks, manifest_or_None)."""
    checks = {
        "agent_folder_exists":      agent_folder.is_dir(),
        "has_manifest_json":        (agent_folder / "manifest.json").is_file(),
        "manifest_parsable":        False,
        "manifest_declares_predict_callable": False,
        "manifest_declares_platform_support": False,
        "has_predict_py":           (agent_folder / "predict.py").is_file(),
        "has_coeffs_json":          (agent_folder / "coeffs.json").is_file(),
        "has_report":               any((agent_folder / n).is_file() for n in ("REPORT.md", "REPORT.txt")),
    }
    manifest = None
    if checks["has_manifest_json"]:
        try:
            manifest = json.loads((agent_folder / "manifest.json").read_text())
            checks["manifest_parsable"] = True
            checks["manifest_declares_predict_callable"] = bool(manifest.get("predict_callable"))
            checks["manifest_declares_platform_support"] = bool(manifest.get("platform_support"))
        except json.JSONDecodeError:
            pass
    return checks, manifest


def run_agent(cfg: dict) -> dict:
    """Execute the full per-agent eval. Returns a complete scorecard dict."""
    sys.path.insert(0, cfg["skill_dir"])
    from traj_metrics import cte_rmse_segment  # noqa: E402

    agent_id = cfg["agent_id"]
    agent_folder = Path(cfg["agent_folder"])
    baseline = cfg["baseline"]
    platform_lookup = cfg["platform_lookup"]
    sample_filter_expr = cfg["sample_filter"]
    truth_col = cfg["truth_channel"]
    grid_step_m = cfg["grid_step_m"]
    min_dist_m = cfg["min_segment_distance_m"]
    timeout_s = cfg.get("timeout_s", 120)

    checks, manifest = format_checks(agent_folder)
    started = time.time()

    base = {
        "agent_id":         agent_id,
        "agent_folder":     str(agent_folder),
        "format_checks":    checks,
        "manifest":         manifest,
        "execution": {
            "status":                  "failed",
            "reason":                  None,
            "n_segments_attempted":    0,
            "n_segments_succeeded":    0,
            "n_segments_skipped_unsupported_platform": 0,
            "n_segments_runtime_error": 0,
            "first_runtime_error":     None,
            "wall_time_seconds":       0.0,
        },
        "yaw_rate":         None,
        "cte":              None,
        "per_platform":     {},
        "per_segment":      [],
        "coefficients":     None,
    }

    # Bail on missing pieces.
    if not checks["agent_folder_exists"]:
        base["execution"]["reason"] = "missing_final_model_dir"
        return base
    if not checks["has_manifest_json"]:
        base["execution"]["reason"] = "missing_manifest_json"
        return base
    if not checks["manifest_parsable"]:
        base["execution"]["reason"] = "manifest_json_invalid"
        return base
    if not checks["has_predict_py"]:
        base["execution"]["reason"] = "missing_predict_py"
        return base

    # Coefficient dump for the calibration card.
    if checks["has_coeffs_json"]:
        try:
            base["coefficients"] = json.loads((agent_folder / "coeffs.json").read_text())
        except json.JSONDecodeError:
            base["coefficients"] = {"_parse_error": True}

    # Import — suppress agent's own stdout/stderr to keep ours clean.
    sink = io.StringIO()
    try:
        with redirect_stdout(sink), redirect_stderr(sink):
            predict = load_predict(agent_folder, manifest)
    except Exception as e:
        base["execution"]["reason"] = "import_failed"
        base["execution"]["first_runtime_error"] = f"{type(e).__name__}: {str(e)[:300]}"
        return base

    # Lazy-import pandas — only once we know we'll need it.
    try:
        import pandas as pd
    except ImportError:
        base["execution"]["reason"] = "pandas_unavailable_in_worker"
        return base

    declared_platforms = set(manifest.get("platform_support", []) or [])
    seg_paths = [Path(p) for p in baseline.get("segment_paths", [])]
    base["execution"]["n_segments_attempted"] = len(seg_paths)

    # Per-platform accumulators for both KPIs.
    pp: dict[str, dict] = {}

    def pp_init(plat: str) -> dict:
        return pp.setdefault(plat, {
            "n_segments": 0, "n_segments_ok": 0, "n_segments_runtime_error": 0,
            "yaw_sum_sq": 0.0, "yaw_n": 0,
            "cte_sum_sq": 0.0, "cte_n_bins": 0, "cte_n_segments_used": 0, "cte_n_segments_short": 0,
        })

    n_ok = 0
    n_unsupported = 0
    n_runtime = 0
    first_err: str | None = None

    fcode = compile(f"({sample_filter_expr})", "<filter>", "eval")

    for seg_path in seg_paths:
        if (time.time() - started) > timeout_s:
            base["execution"]["reason"] = "timeout"
            break

        platform = derive_platform(seg_path, platform_lookup)
        if platform is None:
            n_unsupported += 1
            continue
        if platform not in declared_platforms:
            n_unsupported += 1
            continue

        p_acc = pp_init(platform)
        p_acc["n_segments"] += 1

        try:
            with redirect_stdout(sink), redirect_stderr(sink):
                sim_df = pd.read_csv(seg_path)
                pred_df = predict(sim_df, platform)
        except Exception as e:
            n_runtime += 1
            p_acc["n_segments_runtime_error"] += 1
            if first_err is None:
                first_err = f"{seg_path.name}: {type(e).__name__}: {str(e)[:200]}"
            continue

        if "yaw_rate_pred_rads" not in pred_df.columns:
            n_runtime += 1
            p_acc["n_segments_runtime_error"] += 1
            if first_err is None:
                first_err = f"{seg_path.name}: pred_df missing yaw_rate_pred_rads column"
            continue

        # Yaw RMSE — pooled with sample filter.
        try:
            yr_agent = pred_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
            yr_truth = sim_df[truth_col].to_numpy(dtype=float)
            v_mps = sim_df["v_mps"].to_numpy(dtype=float)
        except (KeyError, ValueError) as e:
            n_runtime += 1
            p_acc["n_segments_runtime_error"] += 1
            if first_err is None:
                first_err = f"{seg_path.name}: column read failed: {e!r}"
            continue

        # NaN-safe pooled accumulation.
        try:
            import numpy as np
            mask = (v_mps > 0)  # placeholder
            mask = np.vectorize(lambda v: eval(fcode, {"v_mps": v, "math": math}))(v_mps)
            mask &= np.isfinite(yr_agent) & np.isfinite(yr_truth)
            d = yr_agent[mask] - yr_truth[mask]
            seg_yaw_sum_sq = float(np.sum(d * d))
            seg_yaw_n = int(d.size)
        except Exception as e:
            n_runtime += 1
            p_acc["n_segments_runtime_error"] += 1
            if first_err is None:
                first_err = f"{seg_path.name}: yaw accumulation failed: {e!r}"
            continue

        # CTE per segment — unfiltered (needs full continuous series).
        try:
            t = sim_df["t_s"].to_numpy(dtype=float)
            seg_cte_sum_sq, seg_cte_n_bins, _total = cte_rmse_segment(
                t, v_mps, yr_truth, yr_agent,
                grid_step_m=grid_step_m, min_distance_m=min_dist_m,
            )
        except Exception as e:
            n_runtime += 1
            p_acc["n_segments_runtime_error"] += 1
            if first_err is None:
                first_err = f"{seg_path.name}: cte failed: {e!r}"
            continue

        # Tally.
        p_acc["yaw_sum_sq"] += seg_yaw_sum_sq
        p_acc["yaw_n"] += seg_yaw_n
        p_acc["cte_sum_sq"] += seg_cte_sum_sq
        p_acc["cte_n_bins"] += seg_cte_n_bins
        if seg_cte_n_bins == 0:
            p_acc["cte_n_segments_short"] += 1
        else:
            p_acc["cte_n_segments_used"] += 1
        p_acc["n_segments_ok"] += 1
        n_ok += 1

        seg_yaw_rmse = math.sqrt(seg_yaw_sum_sq / seg_yaw_n) if seg_yaw_n else None
        seg_cte_rmse = math.sqrt(seg_cte_sum_sq / seg_cte_n_bins) if seg_cte_n_bins else None
        base["per_segment"].append({
            "segment": str(seg_path),
            "platform": platform,
            "yaw_rmse": seg_yaw_rmse,
            "cte_rmse_m": seg_cte_rmse,
            "n_yaw_samples": seg_yaw_n,
            "n_cte_bins": seg_cte_n_bins,
        })

    # Pool across platforms.
    yaw_sum_sq_total = sum(p["yaw_sum_sq"] for p in pp.values())
    yaw_n_total = sum(p["yaw_n"] for p in pp.values())
    cte_sum_sq_total = sum(p["cte_sum_sq"] for p in pp.values())
    cte_n_bins_total = sum(p["cte_n_bins"] for p in pp.values())

    base["execution"]["n_segments_succeeded"] = n_ok
    base["execution"]["n_segments_skipped_unsupported_platform"] = n_unsupported
    base["execution"]["n_segments_runtime_error"] = n_runtime
    base["execution"]["first_runtime_error"] = first_err
    base["execution"]["wall_time_seconds"] = round(time.time() - started, 2)

    if n_ok == 0:
        base["execution"]["reason"] = base["execution"]["reason"] or "no_segments_succeeded"
        return base

    yaw_baseline = baseline["yaw_rate"]["rmse_rad_per_s"]
    cte_baseline = baseline["cte"]["rmse_meters"]

    yaw_rmse = math.sqrt(yaw_sum_sq_total / yaw_n_total) if yaw_n_total else None
    cte_rmse = math.sqrt(cte_sum_sq_total / cte_n_bins_total) if cte_n_bins_total else None

    base["yaw_rate"] = {
        "baseline_rmse":    yaw_baseline,
        "agent_rmse":       yaw_rmse,
        "improvement_pct":  ((yaw_baseline - yaw_rmse) / yaw_baseline * 100) if yaw_rmse is not None else None,
        "n_samples":        yaw_n_total,
    }
    base["cte"] = {
        "baseline_rmse_meters": cte_baseline,
        "agent_rmse_meters":    cte_rmse,
        "improvement_pct":      ((cte_baseline - cte_rmse) / cte_baseline * 100) if cte_rmse is not None else None,
        "n_distance_bins":      cte_n_bins_total,
        "n_segments_used":      sum(p["cte_n_segments_used"] for p in pp.values()),
        "n_segments_short":     sum(p["cte_n_segments_short"] for p in pp.values()),
    }
    # Per-platform pooled RMSE for the bonus per-platform breakdown.
    for plat, p in pp.items():
        plat_block: dict = {
            "n_segments":               p["n_segments"],
            "n_segments_ok":            p["n_segments_ok"],
            "n_segments_runtime_error": p["n_segments_runtime_error"],
            "yaw_rate": None,
            "cte": None,
        }
        if p["yaw_n"]:
            yrmse = math.sqrt(p["yaw_sum_sq"] / p["yaw_n"])
            plat_block["yaw_rate"] = {
                "agent_rmse":      yrmse,
                "n_samples":       p["yaw_n"],
            }
        if p["cte_n_bins"]:
            crmse = math.sqrt(p["cte_sum_sq"] / p["cte_n_bins"])
            plat_block["cte"] = {
                "agent_rmse_meters": crmse,
                "n_distance_bins":   p["cte_n_bins"],
                "n_segments_used":   p["cte_n_segments_used"],
            }
        base["per_platform"][plat] = plat_block

    base["execution"]["status"] = "ok"
    base["execution"]["reason"] = None
    return base


def main():
    try:
        cfg = json.loads(sys.stdin.read())
    except Exception as e:
        sys.stderr.write(f"worker: bad stdin config: {e!r}\n")
        sys.exit(2)

    try:
        result = run_agent(cfg)
    except Exception:
        sys.stderr.write("worker: unexpected exception:\n")
        sys.stderr.write(traceback.format_exc())
        sys.exit(2)

    sys.stdout.write(json.dumps(result, default=str))
    sys.exit(0 if result["execution"]["status"] == "ok" else 1)


if __name__ == "__main__":
    main()
