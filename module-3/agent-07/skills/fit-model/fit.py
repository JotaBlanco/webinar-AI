"""Model-agnostic fitter — minimise an objective (yaw RMSE, CTE RMSE, or a
blend) over per-platform coefficient dicts.

The skill never sees the model. The agent supplies a `predict_factory`
that, given a platform and its coefficient dict, returns a Python callable
mapping `sim_df -> ndarray` of yaw-rate predictions. The factory can wrap
any model the agent likes — bicycle / understeer / cubic / lookup table —
and can change shape between calls. The fitter just calls it.

Optimisation is **per-platform and independent** — each platform's
parameter vector is optimised against that platform's segments. This
matches the lateral-fidelity task structure (per-platform calibration)
and keeps the optimisation low-dimensional.

The objective is one of:
  - "yaw"          : pooled, v-filtered yaw-rate RMSE (rad/s)
  - "cte"          : pooled, distance-bin CTE RMSE (m)
  - "yaw_plus_cte" : yaw_rmse + cte_weight * (cte_rmse / 1000)
                     — keeps both on a comparable scale; tune cte_weight if
                     your platforms have very different CTE magnitudes.

Truth columns and the V0 baseline alias are resolved per platform via
`scoring-model`'s `PLATFORM_SCHEMA`, so Tesla (or any platform whose
sim.csv uses a non-default column name) fits cleanly instead of being
silently dropped.
"""

from __future__ import annotations

import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize  # type: ignore

# Reuse the schema + allowlist + path helper from scoring-model so the two
# skills can't drift. If you move the schema, update this import.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "score-model"))
from score import (  # noqa: E402
    ALLOWED_INPUT_COLUMNS,
    DEFAULT_SCHEMA,
    PLATFORM_SCHEMA,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from traj_metrics import cte_diagnostics_segment  # noqa: E402


# ---------------------------------------------------------------------------
# Path helper duplicated locally (kept small on purpose). If you change the
# segment layout (`<root>/<PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv`),
# update BOTH scoring-model and this helper.
# ---------------------------------------------------------------------------

def _platform_from_path(p: Path) -> str:
    return p.resolve().parents[3].name


def _resolve_schema(platform: str) -> dict:
    return PLATFORM_SCHEMA.get(platform, DEFAULT_SCHEMA)


def _bucket_by_platform(seg_paths) -> dict[str, list[Path]]:
    buckets: dict[str, list[Path]] = defaultdict(list)
    for p in seg_paths:
        buckets[_platform_from_path(Path(p))].append(Path(p))
    return dict(buckets)


# ---------------------------------------------------------------------------
# Segment pre-load — read each sim.csv once, build the sim_df_agent view
# (allowlist + baseline alias), cache the numpy arrays the objective needs.
# This collapses the per-iteration cost of optimisation to "call predict,
# vector-diff against truth".
# ---------------------------------------------------------------------------

def _preload(segment_paths: list[Path]) -> list[dict]:
    out: list[dict] = []
    for p in segment_paths:
        platform = _platform_from_path(p)
        schema = _resolve_schema(platform)
        try:
            df = pd.read_csv(p)
        except Exception:
            continue

        truth_col = schema["truth_col"]
        if any(c not in df.columns for c in (truth_col, "v_mps", "t_s")):
            continue

        t = df["t_s"].to_numpy(dtype=float)
        if len(t) < 2 or np.any(np.diff(t) <= 0):
            continue

        sim_df_agent = df[[c for c in df.columns if c in ALLOWED_INPUT_COLUMNS]].copy()
        baseline_col = schema["baseline_col"]
        if "yaw_rate_pred_rads" not in sim_df_agent.columns and baseline_col in df.columns:
            sim_df_agent["yaw_rate_pred_rads"] = df[baseline_col].astype(float).to_numpy()

        out.append({
            "path":         p,
            "platform":     platform,
            "sim_df_agent": sim_df_agent,
            "t":            t,
            "v":            df["v_mps"].to_numpy(dtype=float),
            "truth":        df[truth_col].to_numpy(dtype=float),
        })
    return out


# ---------------------------------------------------------------------------
# Objective evaluation — runs the supplied predict callable over one
# platform's pre-loaded segments and returns a scalar.
# ---------------------------------------------------------------------------

def _evaluate(
    preloaded: list[dict],
    predict_callable,
    kind: str,
    v_floor: float,
    grid_step_m: float,
    min_distance_m: float,
    cte_weight: float,
) -> float:
    sum_sq_yaw = 0.0
    n_yaw      = 0
    sum_sq_cte = 0.0
    n_cte      = 0

    for s in preloaded:
        try:
            yr_pred = predict_callable(s["sim_df_agent"])
        except Exception:
            return float("inf")
        yr_pred = np.asarray(yr_pred, dtype=float)
        if yr_pred.shape != s["truth"].shape:
            return float("inf")
        if not np.all(np.isfinite(yr_pred)):
            return float("inf")

        resid = yr_pred - s["truth"]
        mask  = s["v"] > v_floor
        sum_sq_yaw += float(np.sum(resid[mask] ** 2))
        n_yaw      += int(mask.sum())

        if kind in ("cte", "yaw_plus_cte"):
            cte = cte_diagnostics_segment(
                s["t"], s["v"], s["truth"], yr_pred,
                grid_step_m=grid_step_m,
                min_distance_m=min_distance_m,
            )
            sum_sq_cte += cte["sum_sq_m2"]
            n_cte      += cte["n_bins"]

    yaw_rmse = math.sqrt(sum_sq_yaw / n_yaw) if n_yaw > 0 else float("inf")
    cte_rmse = math.sqrt(sum_sq_cte / n_cte) if n_cte > 0 else float("inf")

    if kind == "yaw":
        return yaw_rmse
    if kind == "cte":
        return cte_rmse
    if kind == "yaw_plus_cte":
        # Normalise CTE roughly to the yaw scale so cte_weight=1 is meaningful.
        return yaw_rmse + cte_weight * (cte_rmse / 1000.0)
    raise ValueError(f"unknown objective: {kind!r}")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fit(
    predict_factory,
    initial_coeffs: dict,
    train_segments,
    objective: str = "yaw",
    dev_segments=None,
    bounds: dict | None = None,
    method: str | None = None,
    max_iter: int = 200,
    sample_filter_v_mps: float = 2.0,
    grid_step_m: float = 1.0,
    min_distance_m: float = 20.0,
    cte_weight: float = 1.0,
    verbose: bool = False,
) -> dict:
    """Fit per-platform coefficients against an objective.

    Args:
        predict_factory: callable(platform: str, coeffs: dict[str, float])
            -> callable(sim_df: pd.DataFrame) -> ndarray[len(sim_df)].
            Returns a yaw-rate prediction array. The factory may close over
            anything — the fitter never inspects the model.
        initial_coeffs: {platform: {param_name: float}}. Defines the
            optimisation variables. Parameter order is the dict order.
        train_segments: list[Path] OR {platform: list[Path]}. If a flat list,
            segments are bucketed by platform via the standard path layout.
        objective: "yaw" | "cte" | "yaw_plus_cte".
        dev_segments: optional held-out segments scored once after fit, in
            the same format as train_segments.
        bounds: {platform: {param_name: (lo, hi)}} or None. If set,
            method defaults to "L-BFGS-B"; otherwise "Nelder-Mead".
        method: scipy.optimize.minimize method name. Auto if None.
        max_iter: scipy `maxiter`.
        sample_filter_v_mps, grid_step_m, min_distance_m: passed through.
        cte_weight: weighting for the "yaw_plus_cte" blend (CTE is divided by
            1000 before weighting to match yaw scale roughly).
        verbose: print one line per iteration.

    Returns:
        dict with keys:
          - coeffs:     {platform: {param: float}}  fitted coefficients
          - train_obj:  {platform: float}           final objective on train
          - dev_obj:    {platform: float} or None   final objective on dev
          - history:    {platform: [{x, obj}, ...]} optimisation trace
          - n_iter:     {platform: int}             scipy iteration count
          - converged:  {platform: bool}            scipy `success`
          - objective:  the objective name passed in
    """
    if objective not in ("yaw", "cte", "yaw_plus_cte"):
        raise ValueError(f"unknown objective: {objective!r}")

    if isinstance(train_segments, list):
        train_by_plat = _bucket_by_platform(train_segments)
    else:
        train_by_plat = {p: [Path(x) for x in lst] for p, lst in train_segments.items()}

    dev_by_plat: dict[str, list[Path]] = {}
    if dev_segments is not None:
        if isinstance(dev_segments, list):
            dev_by_plat = _bucket_by_platform(dev_segments)
        else:
            dev_by_plat = {p: [Path(x) for x in lst] for p, lst in dev_segments.items()}

    coeffs_out:    dict[str, dict] = {}
    train_obj:     dict[str, float] = {}
    dev_obj:       dict[str, float] = {}
    history:       dict[str, list] = {}
    n_iter:        dict[str, int] = {}
    converged:     dict[str, bool] = {}

    for platform, init in initial_coeffs.items():
        plat_train = train_by_plat.get(platform, [])
        preloaded = _preload(plat_train)
        if not preloaded:
            coeffs_out[platform] = dict(init)
            train_obj[platform]  = float("nan")
            history[platform]    = []
            n_iter[platform]     = 0
            converged[platform]  = False
            if verbose:
                print(f"[fit-model] {platform}: no usable train segments — passthrough init.")
            continue

        param_names = list(init.keys())
        x0 = np.array([float(init[k]) for k in param_names], dtype=float)

        plat_bounds = None
        if bounds and platform in bounds:
            plat_bounds = [bounds[platform].get(k, (None, None)) for k in param_names]

        chosen_method = method or ("L-BFGS-B" if plat_bounds else "Nelder-Mead")
        trace: list[dict] = []

        def fun(x, _platform=platform, _names=param_names, _segs=preloaded):
            coeffs = dict(zip(_names, x.tolist()))
            try:
                cb = predict_factory(_platform, coeffs)
            except Exception:
                return float("inf")
            val = _evaluate(
                _segs, cb, objective,
                sample_filter_v_mps, grid_step_m, min_distance_m, cte_weight,
            )
            trace.append({"x": x.tolist(), "obj": val})
            if verbose:
                pretty = ", ".join(f"{k}={v:+.5g}" for k, v in coeffs.items())
                print(f"[fit-model] {_platform}: obj={val:.6f}  ({pretty})")
            return val

        try:
            res = minimize(
                fun, x0,
                method=chosen_method,
                bounds=plat_bounds,
                options={"maxiter": max_iter, "disp": verbose},
            )
            coeffs_out[platform] = dict(zip(param_names, res.x.tolist()))
            train_obj[platform]  = float(res.fun)
            n_iter[platform]     = int(getattr(res, "nit", len(trace)))
            converged[platform]  = bool(getattr(res, "success", False))
        except Exception as e:
            coeffs_out[platform] = dict(init)
            train_obj[platform]  = float("inf")
            n_iter[platform]     = 0
            converged[platform]  = False
            if verbose:
                print(f"[fit-model] {platform}: scipy raised — {e!r}")

        history[platform] = trace

        plat_dev = dev_by_plat.get(platform, [])
        if plat_dev:
            dev_pre = _preload(plat_dev)
            if dev_pre:
                cb_final = predict_factory(platform, coeffs_out[platform])
                dev_obj[platform] = _evaluate(
                    dev_pre, cb_final, objective,
                    sample_filter_v_mps, grid_step_m, min_distance_m, cte_weight,
                )

    return {
        "coeffs":    coeffs_out,
        "train_obj": train_obj,
        "dev_obj":   dev_obj if dev_by_plat else None,
        "history":   history,
        "n_iter":    n_iter,
        "converged": converged,
        "objective": objective,
    }


# ---------------------------------------------------------------------------
# Display helper
# ---------------------------------------------------------------------------

def format_fit_summary(result: dict) -> str:
    L = []
    L.append("## fit-model summary")
    L.append(f"- objective: `{result['objective']}`")
    L.append("")
    has_dev = result.get("dev_obj") is not None
    header = "| platform | converged | n_iter | train_obj"
    sep    = "|---|---|---|---"
    if has_dev:
        header += " | dev_obj"
        sep    += "|---"
    header += " | coeffs |"
    sep    += "|---|"
    L.append(header)
    L.append(sep)
    for plat, coeffs in result["coeffs"].items():
        tr = result["train_obj"].get(plat, float("nan"))
        nit = result["n_iter"].get(plat, 0)
        conv = "✓" if result["converged"].get(plat) else "✗"
        cells = [f"`{plat}`", conv, str(nit), f"{tr:.6f}" if tr == tr else "nan"]
        if has_dev:
            dv = result["dev_obj"].get(plat, float("nan"))
            cells.append(f"{dv:.6f}" if dv == dv else "nan")
        pretty = ", ".join(f"{k}={v:+.5g}" for k, v in coeffs.items())
        cells.append(f"`{{{pretty}}}`")
        L.append("| " + " | ".join(cells) + " |")
    return "\n".join(L)


__all__ = ["fit", "format_fit_summary"]
