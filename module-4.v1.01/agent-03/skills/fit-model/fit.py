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
# Post-fit diagnostics — degeneracy / overfit / co-collapse heuristics.
#
# These run on the fitted vector and the optimisation trace. They cannot
# prove the model is identifiable; they only warn when symptoms of a
# common failure mode are present, so the agent looks before shipping.
# ---------------------------------------------------------------------------

# Tunables. Edit if your problem's natural scale is different.
COLLAPSE_REL_THRESHOLD = 0.05   # final |x| < this × initial |x|
COLLAPSE_ABS_THRESHOLD = 1e-3   # final |x| also below this absolute floor
OVERFIT_GAP_FRACTION   = 0.50   # dev_obj > (1 + this) × train_obj  → "wide gap"
NEAR_BOUND_FRACTION    = 0.02   # within this much of a bound → "stuck on bound"


def _detect_diagnostics(
    *,
    platform: str,
    param_names: list[str],
    x0: np.ndarray,
    x_final: np.ndarray,
    train_obj: float,
    dev_obj: float | None,
    bounds: list | None,
    converged: bool,
) -> list[dict]:
    """Return a list of {kind, severity, msg} warnings for this platform's fit."""
    out: list[dict] = []

    # --- Co-collapse: multiple params shrunk near zero from a non-zero start ---
    collapsed = []
    for name, xi, xf in zip(param_names, x0, x_final):
        if abs(xi) > 1e-9 and abs(xf) < COLLAPSE_ABS_THRESHOLD and abs(xf) < abs(xi) * COLLAPSE_REL_THRESHOLD:
            collapsed.append(name)
    if len(collapsed) >= 2:
        out.append({
            "kind":     "co_collapse",
            "severity": "high",
            "params":   collapsed,
            "msg":      (
                f"{len(collapsed)} parameters collapsed near zero ({collapsed}). "
                f"Common cause: two coefficients enter the model in a co-degenerate "
                f"way (e.g. gain × L_eff both free with no anchor), so the optimiser "
                f"finds a numerically-equivalent but physically nonsensical solution. "
                f"Fixes: remove one parameter, add a physical bound, or fix one of them."
            ),
        })

    # --- Stuck on a bound: any final |x - bound| / span < NEAR_BOUND_FRACTION ---
    if bounds is not None:
        on_bound = []
        for name, xf, b in zip(param_names, x_final, bounds):
            if b is None: continue
            lo, hi = b
            span = (hi - lo) if (lo is not None and hi is not None and hi > lo) else 1.0
            if lo is not None and abs(xf - lo) < NEAR_BOUND_FRACTION * span:
                on_bound.append((name, "lower", lo))
            elif hi is not None and abs(xf - hi) < NEAR_BOUND_FRACTION * span:
                on_bound.append((name, "upper", hi))
        if on_bound:
            out.append({
                "kind":     "stuck_on_bound",
                "severity": "warn",
                "params":   on_bound,
                "msg":      (
                    f"{len(on_bound)} parameter(s) ended on a bound: {on_bound}. "
                    f"The true optimum may be outside; widen the bound (carefully) "
                    f"or confirm this is the physical limit you intended."
                ),
            })

    # --- Wide train/dev gap (overfit symptom) — only if dev was scored. ---
    if dev_obj is not None and train_obj == train_obj and dev_obj == dev_obj:
        if train_obj > 0 and dev_obj > (1.0 + OVERFIT_GAP_FRACTION) * train_obj:
            sev = "high" if dev_obj > 2.0 * train_obj else "warn"
            out.append({
                "kind":     "wide_train_dev_gap",
                "severity": sev,
                "msg":      (
                    f"dev_obj ({dev_obj:.6f}) is more than "
                    f"{OVERFIT_GAP_FRACTION:+.0%} above train_obj ({train_obj:.6f}). "
                    f"Likely overfit / route-leakage / model too flexible. "
                    f"Consider fewer parameters, regularisation, or better train/dev split."
                ),
            })

    # --- Optimiser said it did not converge. ---
    if not converged:
        out.append({
            "kind":     "did_not_converge",
            "severity": "warn",
            "msg":      "scipy.optimize.minimize returned success=False. Trust the fit only if dev_obj agrees with train_obj.",
        })

    return out


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
          - coeffs:        {platform: {param: float}}  fitted coefficients
          - train_obj:     {platform: float}           final objective on train
          - dev_obj:       {platform: float} or None   final objective on dev
          - gap:           {platform: float} or None   dev_obj - train_obj
          - gap_fraction:  {platform: float} or None   (dev_obj - train_obj) / train_obj
          - warnings:      {platform: [diag dict, ...]} co-collapse / overfit /
                           stuck-on-bound / didn't-converge flags
          - history:       {platform: [{x, obj}, ...]} optimisation trace
          - n_iter:        {platform: int}             scipy iteration count
          - converged:     {platform: bool}            scipy `success`
          - objective:     the objective name passed in
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
    gap:           dict[str, float] = {}
    gap_fraction:  dict[str, float] = {}
    warnings_out:  dict[str, list]  = {}
    history:       dict[str, list] = {}
    n_iter:        dict[str, int] = {}
    converged:     dict[str, bool] = {}

    for platform, init in initial_coeffs.items():
        plat_train = train_by_plat.get(platform, [])
        preloaded = _preload(plat_train)
        if not preloaded:
            coeffs_out[platform]   = dict(init)
            train_obj[platform]    = float("nan")
            warnings_out[platform] = []
            history[platform]      = []
            n_iter[platform]       = 0
            converged[platform]    = False
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
        plat_dev_obj: float | None = None
        if plat_dev:
            dev_pre = _preload(plat_dev)
            if dev_pre:
                cb_final = predict_factory(platform, coeffs_out[platform])
                plat_dev_obj = _evaluate(
                    dev_pre, cb_final, objective,
                    sample_filter_v_mps, grid_step_m, min_distance_m, cte_weight,
                )
                dev_obj[platform] = plat_dev_obj
                tr = train_obj[platform]
                if tr == tr and plat_dev_obj == plat_dev_obj:
                    gap[platform] = float(plat_dev_obj - tr)
                    if tr > 1e-12:
                        gap_fraction[platform] = float((plat_dev_obj - tr) / tr)
                    elif plat_dev_obj < 1e-9:
                        # Both essentially zero (e.g. Tesla passthrough) — gap is zero.
                        gap_fraction[platform] = 0.0
                    else:
                        gap_fraction[platform] = float("inf")

        # Post-fit diagnostics on this platform's run.
        x_final = np.array([coeffs_out[platform][k] for k in param_names], dtype=float)
        warnings_out[platform] = _detect_diagnostics(
            platform=platform,
            param_names=param_names,
            x0=x0,
            x_final=x_final,
            train_obj=train_obj[platform],
            dev_obj=plat_dev_obj,
            bounds=plat_bounds,
            converged=converged[platform],
        )

    return {
        "coeffs":       coeffs_out,
        "train_obj":    train_obj,
        "dev_obj":      dev_obj if dev_by_plat else None,
        "gap":          gap if dev_by_plat else None,
        "gap_fraction": gap_fraction if dev_by_plat else None,
        "warnings":     warnings_out,
        "history":      history,
        "n_iter":       n_iter,
        "converged":    converged,
        "objective":    objective,
    }


# ---------------------------------------------------------------------------
# Display helper
# ---------------------------------------------------------------------------

def format_fit_summary(result: dict) -> str:
    """Render a one-shot markdown dashboard. Opens with warnings (if any),
    then the per-platform table with train/dev/gap columns."""
    L = []
    L.append("## fit-model summary")
    L.append(f"- objective: `{result['objective']}`")

    # --- Warnings block — surfaced FIRST so the agent sees co-collapse / overfit
    # before they look at the numbers. ---
    warn_total = sum(len(w) for w in (result.get("warnings") or {}).values())
    if warn_total:
        L.append("")
        L.append("### 🚨 fit warnings — READ BEFORE shipping")
        L.append("These do not block the fit; they flag failure modes the optimiser cannot detect on its own.")
        L.append("")
        for plat, ws in result["warnings"].items():
            if not ws: continue
            for w in ws:
                tag = "🚨" if w.get("severity") == "high" else "⚠️"
                L.append(f"- {tag} `{plat}` — **{w['kind']}**: {w['msg']}")

    L.append("")
    has_dev = result.get("dev_obj") is not None
    header = "| platform | converged | warn | n_iter | train_obj"
    sep    = "|---|---|---|---|---"
    if has_dev:
        header += " | dev_obj | gap | gap_% "
        sep    += "|---|---|---"
    header += " | coeffs |"
    sep    += "|---|"
    L.append(header)
    L.append(sep)
    for plat, coeffs in result["coeffs"].items():
        tr   = result["train_obj"].get(plat, float("nan"))
        nit  = result["n_iter"].get(plat, 0)
        conv = "✓" if result["converged"].get(plat) else "✗"
        ws   = result.get("warnings", {}).get(plat, [])
        # Aggregate per-platform warning marker: 🚨 if any high, ⚠️ if any warn, else ok.
        if any(w.get("severity") == "high" for w in ws):
            warn_cell = "🚨"
        elif any(w.get("severity") == "warn" for w in ws):
            warn_cell = "⚠️"
        else:
            warn_cell = "ok"
        cells = [f"`{plat}`", conv, warn_cell, str(nit), f"{tr:.6f}" if tr == tr else "nan"]
        if has_dev:
            dv = result["dev_obj"].get(plat, float("nan"))
            g  = result.get("gap", {}).get(plat, float("nan"))
            gf = result.get("gap_fraction", {}).get(plat, float("nan"))
            cells.append(f"{dv:.6f}" if dv == dv else "nan")
            cells.append(f"{g:+.6f}" if g == g else "nan")
            # Flag any single platform's gap inline too — easier to scan a wide table.
            if gf == gf and gf > OVERFIT_GAP_FRACTION:
                cells.append(f"**{gf:+.1%}** ⚠️")
            elif gf == gf:
                cells.append(f"{gf:+.1%}")
            else:
                cells.append("nan")
        pretty = ", ".join(f"{k}={v:+.5g}" for k, v in coeffs.items())
        cells.append(f"`{{{pretty}}}`")
        L.append("| " + " | ".join(cells) + " |")

    if has_dev:
        L.append("")
        L.append(f"`gap_%` = (dev - train) / train. Inline ⚠️ when > {OVERFIT_GAP_FRACTION:+.0%}.")

    return "\n".join(L)


__all__ = [
    "fit",
    "format_fit_summary",
    "COLLAPSE_REL_THRESHOLD",
    "COLLAPSE_ABS_THRESHOLD",
    "OVERFIT_GAP_FRACTION",
    "NEAR_BOUND_FRACTION",
]
