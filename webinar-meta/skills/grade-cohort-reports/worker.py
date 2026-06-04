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


# --- Operating contract --------------------------------------------------------
# Columns the agent's predict() is allowed to see. Everything else is stripped
# from sim_df at the boundary before predict() is called. This enforces the
# operating contract: no inference-time access to truth or truth-derived signals.
#
# Reasoning per column:
#   t_s, delta_wheel_deg, delta_road_rad, v_mps, a_long_mps2 — physical sensor
#       channels available in production from CAN bus / EPS / wheel-speeds / IMU
#       longitudinal axis. Legitimate inputs.
#   accel_pedal_pct, brake_pressed — driver inputs.
#   yaw_rate_pred_rads — V0 baseline prediction. The column the agent is
#       REPLACING — they can read it as a reference. Not truth.
#
# Stripped (each is either truth, truth-derived, or simulator internal state):
#   yaw_rate_meas_rads      — the TRUTH channel the eval scores against
#   a_lat_meas_mps2         — kinematically = v * yaw_rate; effectively truth
#                             through the sim's construction. (In a real car
#                             this would be a separate IMU axis, but in THIS
#                             dataset it was computed from the truth yaw rate.)
#   yaw_rate_resid_rads     — V0_pred - truth; a direct truth leak
#   a_y_resid_mps2          — same as above for lateral acc
#   x_m, y_m, psi_rad       — simulator's integrated state (depends on truth path)
#   v_state_mps, delta_state_rad — simulator internal state
#   a_y_pred_mps2           — V0 lateral acc prediction (not a leak, but unused;
#                             stripping for cleanliness — add it back if needed)
ALLOWED_INPUT_COLUMNS = frozenset({
    "t_s",
    "delta_wheel_deg",
    "delta_road_rad",
    "v_mps",
    "a_long_mps2",
    "accel_pedal_pct",
    "brake_pressed",
    "yaw_rate_pred_rads",
})

# Columns whose appearance in predict.py source is a strong signal of a leak
# attempt. Reported as `column_leak_detected` for auditing; the agent still
# gets scored (the allowlist strip means the leak can't actually fire).
TRUTH_OR_DERIVED_COLUMN_NAMES = (
    "yaw_rate_meas_rads",
    "a_lat_meas_mps2",
    "yaw_rate_resid_rads",
    "a_y_resid_mps2",
)


def strip_to_allowlist(df, allowed: frozenset[str]) -> tuple["pandas.DataFrame", list[str]]:
    """Return (df_with_only_allowed_columns, stripped_column_names)."""
    stripped = [c for c in df.columns if c not in allowed]
    return df[[c for c in df.columns if c in allowed]], stripped


def static_scan_for_leak(predict_path: Path, predict_fn_name: str = "predict") -> dict:
    """Read predict.py source and look for references to truth/derived column names.

    Uses AST to locate the predict() function's source byte range (handles
    multi-line signatures, type hints, decorators, anything). Buckets hits:
      - inside the predict() function body (likely inference-time leak)
      - inside any helper called from predict() (transitive — also a leak)
      - elsewhere in the file (docstring / __main__ / training notes — not a leak)
    """
    import ast
    try:
        source = predict_path.read_text(errors="replace")
    except Exception:
        return {"scan_ok": False, "hits_in_predict_body": {}, "hits_in_helpers": {}, "hits_elsewhere": {}}

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {"scan_ok": False, "hits_in_predict_body": {}, "hits_in_helpers": {}, "hits_elsewhere": {}}

    src_lines = source.splitlines(keepends=True)
    line_offsets = [0]
    for ln in src_lines:
        line_offsets.append(line_offsets[-1] + len(ln))

    def node_range(node: ast.AST) -> tuple[int, int]:
        s = line_offsets[node.lineno - 1] + node.col_offset
        if hasattr(node, "end_lineno") and node.end_lineno is not None:
            e = line_offsets[node.end_lineno - 1] + (node.end_col_offset or 0)
        else:
            e = len(source)
        return s, e

    # Find the predict() function definition + any other top-level function defs.
    predict_fn = None
    all_fns: dict[str, ast.FunctionDef] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            all_fns[node.name] = node
            if node.name == predict_fn_name and predict_fn is None:
                predict_fn = node

    helper_names: set[str] = set()
    if predict_fn is not None:
        # Any Name node referenced INSIDE predict_fn that maps to a defined helper.
        for sub in ast.walk(predict_fn):
            if isinstance(sub, ast.Name) and sub.id in all_fns and sub.id != predict_fn_name:
                helper_names.add(sub.id)

    # Compute byte ranges.
    predict_range = node_range(predict_fn) if predict_fn else None
    helper_ranges = [node_range(all_fns[h]) for h in helper_names]

    def in_ranges(idx: int, ranges: list[tuple[int, int]]) -> bool:
        return any(s <= idx < e for s, e in ranges)

    hits_body: dict[str, int] = {}
    hits_helpers: dict[str, int] = {}
    hits_rest: dict[str, int] = {}
    for col in TRUTH_OR_DERIVED_COLUMN_NAMES:
        pat = re.compile(r'["\']' + re.escape(col) + r'["\']')
        n_body = n_helpers = n_rest = 0
        for m in pat.finditer(source):
            idx = m.start()
            if predict_range and predict_range[0] <= idx < predict_range[1]:
                n_body += 1
            elif in_ranges(idx, helper_ranges):
                n_helpers += 1
            else:
                n_rest += 1
        if n_body:
            hits_body[col] = n_body
        if n_helpers:
            hits_helpers[col] = n_helpers
        if n_rest:
            hits_rest[col] = n_rest
    return {
        "scan_ok": True,
        "hits_in_predict_body": hits_body,
        "hits_in_helpers": hits_helpers,
        "hits_elsewhere": hits_rest,
        "helpers_called_from_predict": sorted(helper_names),
    }


def derive_platform(seg_path: Path, lookup: dict[str, str]) -> str | None:
    """Find which platform a sim.csv belongs to by looking for a known token in the path."""
    s = str(seg_path)
    for token, name in lookup.items():
        if token in s:
            return name
    return None


def truth_path_for(input_path: Path, input_dir_name: str, truth_dir_name: str) -> Path:
    """Translate <root>/<input_dir_name>/<rest>.csv -> <root>/<truth_dir_name>/<rest>.csv.

    Defence-in-depth: the input CSV (sim-only) contains only allowlist columns.
    Truth lives in a parallel sim/ tree the worker reads separately, so the
    DataFrame passed to predict() literally cannot contain truth columns.
    """
    s = str(input_path)
    needle = "/" + input_dir_name.strip("/") + "/"
    replacement = "/" + truth_dir_name.strip("/") + "/"
    if needle not in s:
        raise ValueError(f"truth_path_for: input_dir_name {input_dir_name!r} not found in {s!r}")
    return Path(s.replace(needle, replacement, 1))


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
    input_dir_name = cfg.get("input_dir_name", "sim/segments")
    truth_dir_name = cfg.get("truth_dir_name", "sim/segments")
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
        # Contract-enforcement diagnostics (always populated).
        "contract": {
            "allowed_input_columns": sorted(ALLOWED_INPUT_COLUMNS),
            "stripped_columns_per_segment": None,   # filled on first segment
            "leak_scan": None,                       # filled below
        },
    }

    # Static-scan the agent's predict.py source for truth column references —
    # purely diagnostic, doesn't block scoring.
    predict_path = agent_folder / "predict.py"
    if predict_path.is_file():
        base["contract"]["leak_scan"] = static_scan_for_leak(predict_path)

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
                # Read INPUT from sim-only (no truth columns by file-system construction).
                sim_df = pd.read_csv(seg_path)
                # Redundant allowlist strip — defence in depth, no-op if input
                # file is already sim-only, but catches any future drift.
                sim_df, stripped = strip_to_allowlist(sim_df, ALLOWED_INPUT_COLUMNS)
                if base["contract"]["stripped_columns_per_segment"] is None:
                    base["contract"]["stripped_columns_per_segment"] = stripped
                # Read TRUTH from a parallel sim/ file. Only the worker reads it;
                # never handed to predict().
                truth_path = truth_path_for(seg_path, input_dir_name, truth_dir_name)
                truth_df = pd.read_csv(truth_path)
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

        # Yaw RMSE — pooled with sample filter. Truth comes from truth_df
        # (parallel sim/ file); v_mps from the agent-facing sim_df.
        try:
            yr_agent = pred_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
            yr_truth = truth_df[truth_col].to_numpy(dtype=float)
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
