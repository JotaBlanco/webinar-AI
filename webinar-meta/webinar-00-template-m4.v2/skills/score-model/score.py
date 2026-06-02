"""Score any predict callable against a list of segment sim.csv files.

Returns the two pooled KPIs plus a rich per-segment table, per-platform
residual stats (signed bias, std, bias fraction), per-route pooling, worst-N
tables, and full distribution stats. All views read off the SAME pass over
the segments — there is no separate "deep" mode.

CTE math is imported from `_shared/traj_metrics.py`.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
from traj_metrics import cte_diagnostics_segment, integrate_trajectory  # noqa: E402


# ---------------------------------------------------------------------------
# Per-platform schema map.
#
# Different platforms in the sim dataset use different column names for
# ground truth and for the V0 baseline output. Score-model resolves this
# per platform so an agent's predict() signature stays uniform and so the
# scorer doesn't silently skip platforms whose schema differs from the
# Ford/Hyundai default.
#
# - truth_col:    the ground-truth yaw-rate channel against which residuals
#                 are computed.
# - baseline_col: the V0 baseline yaw-rate prediction. Score-model maps this
#                 to the canonical `yaw_rate_pred_rads` name in the sim_df
#                 handed to predict(), so an agent's predict can always
#                 reference V0 as `sim_df["yaw_rate_pred_rads"]` regardless
#                 of platform.
# - note:         human-readable caveat surfaced in the dashboard.
#
# To add a platform, append an entry. To change a column for an existing
# platform (column rename upstream), edit the dict. Unknown platforms fall
# through to DEFAULT_SCHEMA below.
# ---------------------------------------------------------------------------
PLATFORM_SCHEMA: dict[str, dict] = {
    "FORD_F_150_LIGHTNING_MK1": {
        "truth_col":    "yaw_rate_meas_rads",
        "baseline_col": "yaw_rate_pred_rads",
        "note":         None,
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "truth_col":    "yaw_rate_meas_rads",
        "baseline_col": "yaw_rate_pred_rads",
        "note":         None,
    },
    "HYUNDAI_IONIQ_5": {
        "truth_col":    "yaw_rate_meas_rads",
        "baseline_col": "yaw_rate_pred_rads",
        "note":         None,
    },
    "TESLA_MODEL_3": {
        "truth_col":    "psi_dot_rads",
        "baseline_col": "psi_dot_rads",
        "note":         "Tesla sim has no independent truth channel — psi_dot_rads IS the V0 KS output. "
                        "Any deviation from V0 will *increase* RMSE on this platform. Treat near-zero "
                        "Tesla RMSE as a sanity check, not a signal to optimise.",
    },
}

DEFAULT_SCHEMA = {
    "truth_col":    "yaw_rate_meas_rads",
    "baseline_col": "yaw_rate_pred_rads",
    "note":         None,
}


# ---------------------------------------------------------------------------
# Operating contract — must match the canonical grader's allowlist.
#
# Your predict(sim_df, platform) function will be called by the canonical
# grader with a sim_df that has been stripped to ONLY these columns. Truth
# channels (yaw_rate_meas_rads, psi_dot_rads), kinematic shadows
# (a_lat_meas_mps2, a_y_mps2), residuals, and simulator state are NOT
# visible at scoring time.
#
# This local score-model enforces the same allowlist so your local RMSE
# reflects what the canonical grader will see. If you accidentally read a
# stripped column, your predict will fail here too — caught in dev, not in
# grading.
#
# Tesla-specific extras (wheel speeds, drive-inverter torque, the alternate
# brake schema) are included so Tesla predictors can read what Tesla
# actually ships in sim.csv.
# ---------------------------------------------------------------------------
ALLOWED_INPUT_COLUMNS = frozenset({
    "t_s",
    "delta_wheel_deg",
    "delta_road_rad",
    "v_mps",
    "a_long_mps2",
    "accel_pedal_pct",
    "brake_pressed",
    "brake_pedal_state",
    "steer_rate_dps",
    "yaw_rate_pred_rads",   # V0 baseline reference — the column your predict REPLACES
    "di_torque_actual_nm",
    "wheel_FL_kph",
    "wheel_FR_kph",
    "wheel_RL_kph",
    "wheel_RR_kph",
})


# ---------------------------------------------------------------------------
# Bias-warning thresholds — used by `bias_warnings()` and surfaced at the
# top of `format_summary()`. Tunable; "🚨" lights up when |bias| > threshold.
# ---------------------------------------------------------------------------
YAW_BIAS_WARN_RAD_S = 0.002    # rad/s of signed yaw residual
CTE_DRIFT_WARN_M    = 5.0      # m of signed CTE drift


# ---------------------------------------------------------------------------
# Path helpers — data/sim/segments/<PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv
# ---------------------------------------------------------------------------

def _platform_from_path(p: Path) -> str:
    return p.resolve().parents[3].name


def _route_from_path(p: Path) -> str:
    return p.resolve().parents[1].name


def _idx_from_path(p: Path) -> str:
    return p.resolve().parents[0].name


def _default_segment_paths() -> list[Path]:
    """Default to ALL platforms under data/sim/segments/ — not just FORD_*.

    Earlier versions of this skill globbed `FORD_*/**/sim.csv` which silently
    excluded Hyundai and Tesla. The current default is platform-agnostic.
    """
    root = Path.cwd() / "data" / "sim" / "segments"
    if not root.exists():
        return []
    return sorted(p for p in root.glob("*/**/sim.csv") if p.is_file())


# ---------------------------------------------------------------------------
# Test-split refusal — defense at the data-access layer.
#
# The frozen test split lives at data/{sim,sim-only}/test/. score() refuses
# to read it unless explicitly invoked with `final=True`, which is only
# allowed by pre-flight-final-model --final. This is the load-bearing claim
# in AGENTS.md's "Test-split discipline" section.
#
# The same check lives in cv.py for the score_cv wrapper, but lives here
# too so any direct score() call is also caught. Defense in depth.
#
# *** LOAD-BEARING LAYOUT ASSUMPTION ***
#
# The marker check below is a substring scan: any path containing
# "sim-only/test" or "sim/test" is denied. If the project's data layout
# ever moves the test split elsewhere — e.g. `data/test-split/`,
# `data/holdout/`, or `data/sim/segments/test/` — the refusal SILENTLY
# NO-OPS and an agent can score on test during the inner loop without
# error. Verify data/README.md's "Expected layout" matches reality
# before every cohort, and edit TEST_SPLIT_MARKER_PARTS if the layout
# changes — but make it loud, not silent.
# ---------------------------------------------------------------------------

TEST_SPLIT_MARKER_PARTS = ("sim-only/test", "sim/test")


class TestSplitDeniedError(RuntimeError):
    """Raised when score() / score_cv() is asked to read the frozen test split
    outside the final preflight gate. See SKILL.md § 'Test split refusal'."""


def _assert_not_test(segment_paths, final: bool) -> None:
    if final or not segment_paths:
        return
    for p in segment_paths:
        s = str(p)
        if any(marker in s for marker in TEST_SPLIT_MARKER_PARTS):
            raise TestSplitDeniedError(
                f"Test-split read attempted on {p}. The test split is reserved "
                "for pre-flight-final-model --final. Use the dev split, or pass "
                "final=True (only allowed from preflight)."
            )


def _resolve_schema(platform: str) -> dict:
    return PLATFORM_SCHEMA.get(platform, DEFAULT_SCHEMA)


# ---------------------------------------------------------------------------
# Regime classification (per row, yaw-rate diagnostic only)
# ---------------------------------------------------------------------------

def _regime_mask(delta_road: np.ndarray, t: np.ndarray) -> dict[str, np.ndarray]:
    straight = np.abs(delta_road) < 0.01
    if len(t) >= 2:
        ddelta_dt = np.gradient(delta_road, t)
    else:
        ddelta_dt = np.zeros_like(delta_road)
    steady = (~straight) & (np.abs(ddelta_dt) < 0.05)
    transient = (~straight) & (~steady)
    return {"straight": straight, "steady": steady, "transient": transient}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def score(
    predict_fn,
    segment_paths: list | None = None,
    platform_filter: str | None = None,
    grid_step_m: float = 1.0,
    min_distance_m: float = 20.0,
    sample_filter_v_mps: float = 2.0,
    top_n: int = 10,
    final: bool = False,
) -> dict:
    """Score a predict callable across segments.

    Args:
        predict_fn: callable(sim_df, platform) -> DataFrame aligned with sim_df.index,
            must contain ``yaw_rate_pred_rads``.
        segment_paths: list of sim.csv paths. If None, glob all
            ``data/sim/segments/*/**/sim.csv`` under cwd (all platforms).
        platform_filter: if set, keep only that platform.
        grid_step_m, min_distance_m: CTE bin spacing and minimum segment length.
        sample_filter_v_mps: yaw-rate RMSE pools rows where ``v_mps`` exceeds this.
        top_n: how many worst-segments to include in the ranked outlier tables.

    Returns:
        See SKILL.md for the full key inventory. Headline keys are
        ``yaw_rate_rmse`` and ``cte_rmse``; everything else is diagnostic.
    """
    if segment_paths is None:
        segment_paths = _default_segment_paths()
    segment_paths = [Path(p) for p in segment_paths]
    _assert_not_test(segment_paths, final=final)
    if platform_filter is not None:
        segment_paths = [p for p in segment_paths if _platform_from_path(p) == platform_filter]

    # Per-segment records — one dict per segment that passed.
    rows: list[dict] = []
    # Pooled regime accumulators (yaw rate only).
    regime_acc = {
        k: {"sum_sq": 0.0, "sum_signed": 0.0, "n": 0}
        for k in ("straight", "steady", "transient")
    }
    # Per-platform failure counter so the diagnostic isn't just a pooled number.
    failed = 0
    failed_by_platform: dict[str, int] = {}
    # Platforms encountered, with schema notes — surfaced in the summary even
    # when the platform scored cleanly.
    platforms_seen: dict[str, dict] = {}

    def _bump_fail(plat: str) -> None:
        nonlocal failed
        failed += 1
        failed_by_platform[plat] = failed_by_platform.get(plat, 0) + 1

    for p in segment_paths:
        platform = _platform_from_path(p)
        schema = _resolve_schema(platform)
        if platform not in platforms_seen:
            platforms_seen[platform] = {"note": schema.get("note"), "schema_known": platform in PLATFORM_SCHEMA}
        truth_col    = schema["truth_col"]
        baseline_col = schema["baseline_col"]

        try:
            sim_df = pd.read_csv(p)
        except Exception:
            _bump_fail(platform)
            continue

        # Required columns — truth, time, speed. Truth column comes from the
        # per-platform schema, not a hardcoded name.
        missing = [c for c in (truth_col, "v_mps", "t_s") if c not in sim_df.columns]
        if missing:
            _bump_fail(platform)
            continue

        # Strip to operating-contract allowlist before handing to the agent's predict.
        # Mirrors what the canonical grader does — local scores match canonical scores.
        sim_df_agent = sim_df[[c for c in sim_df.columns if c in ALLOWED_INPUT_COLUMNS]].copy()

        # Schema-aware baseline alias: ensure predict() always sees a
        # `yaw_rate_pred_rads` column even on platforms whose native baseline
        # column has a different name (e.g. Tesla's `psi_dot_rads`).
        if "yaw_rate_pred_rads" not in sim_df_agent.columns and baseline_col in sim_df.columns:
            sim_df_agent["yaw_rate_pred_rads"] = sim_df[baseline_col].astype(float).to_numpy()

        try:
            pred_df = predict_fn(sim_df_agent, platform)
        except Exception:
            _bump_fail(platform)
            continue

        if (
            not isinstance(pred_df, pd.DataFrame)
            or "yaw_rate_pred_rads" not in pred_df.columns
            or len(pred_df) != len(sim_df)
        ):
            _bump_fail(platform)
            continue

        t        = sim_df["t_s"].to_numpy(dtype=float)
        v        = sim_df["v_mps"].to_numpy(dtype=float)
        yr_truth = sim_df[truth_col].to_numpy(dtype=float)
        yr_pred  = pred_df["yaw_rate_pred_rads"].to_numpy(dtype=float)

        if len(t) < 2 or np.any(np.diff(t) <= 0):
            _bump_fail(platform)
            continue

        # ---- Yaw-rate residual (v-filtered) ----
        mask_v = v > sample_filter_v_mps
        resid = yr_pred - yr_truth
        r_v = resid[mask_v]
        yr_n = int(mask_v.sum())
        yr_sum_sq     = float(np.sum(r_v ** 2))
        yr_sum_signed = float(np.sum(r_v))
        yr_rmse       = math.sqrt(yr_sum_sq / yr_n) if yr_n > 0 else float("nan")
        yr_mean       = yr_sum_signed / yr_n if yr_n > 0 else float("nan")
        yr_std        = float(np.sqrt(max(yr_sum_sq / yr_n - yr_mean ** 2, 0.0))) if yr_n > 0 else float("nan")

        # ---- CTE diagnostics ----
        cte = cte_diagnostics_segment(
            t, v, yr_truth, yr_pred,
            grid_step_m=grid_step_m,
            min_distance_m=min_distance_m,
        )
        cte_rmse        = math.sqrt(cte["sum_sq_m2"] / cte["n_bins"]) if cte["n_bins"] > 0 else float("nan")
        cte_signed_mean = cte["sum_signed_m"] / cte["n_bins"] if cte["n_bins"] > 0 else float("nan")
        cte_abs_mean    = cte["sum_abs_m"]    / cte["n_bins"] if cte["n_bins"] > 0 else float("nan")

        rows.append({
            "segment_path":      str(p),
            "platform":          platform,
            "route":             _route_from_path(p),
            "idx":               _idx_from_path(p),
            "n_samples":         yr_n,
            "distance_m":        cte["total_distance_m"],
            "end_drift_m":       cte["end_drift_m"],
            "yaw_rate_rmse":     yr_rmse,
            "yaw_residual_mean": yr_mean,
            "yaw_residual_std":  yr_std,
            "yaw_sum_sq":        yr_sum_sq,
            "yaw_sum_signed":    yr_sum_signed,
            "cte_rmse":          cte_rmse,
            "cte_signed_mean":   cte_signed_mean,
            "cte_abs_mean":      cte_abs_mean,
            "cte_sum_sq":        cte["sum_sq_m2"],
            "cte_sum_signed":    cte["sum_signed_m"],
            "cte_n_bins":        cte["n_bins"],
        })

        # ---- Regime split (yaw rate only) ----
        if "delta_road_rad" in sim_df.columns:
            regime_masks = _regime_mask(sim_df["delta_road_rad"].to_numpy(dtype=float), t)
        else:
            regime_masks = {
                "straight": np.zeros_like(v, dtype=bool),
                "steady":   np.zeros_like(v, dtype=bool),
                "transient": np.ones_like(v, dtype=bool),
            }
        for regime, rmask in regime_masks.items():
            combined = rmask & mask_v
            if combined.any():
                rr = resid[combined]
                regime_acc[regime]["sum_sq"]     += float(np.sum(rr ** 2))
                regime_acc[regime]["sum_signed"] += float(np.sum(rr))
                regime_acc[regime]["n"]          += int(combined.sum())

    # Empty case: nothing scored.
    if not rows:
        return _empty_result(failed, failed_by_platform, platforms_seen)

    seg = pd.DataFrame(rows)

    # ---- Overall pooled ----
    overall_yaw_rmse = math.sqrt(seg["yaw_sum_sq"].sum() / seg["n_samples"].sum())
    overall_cte_rmse = math.sqrt(seg["cte_sum_sq"].sum() / seg["cte_n_bins"].sum()) if seg["cte_n_bins"].sum() > 0 else float("nan")

    # ---- Per-platform pooled (re-derive from per-segment sums) ----
    per_platform = {}
    for platform, sub in seg.groupby("platform"):
        n      = int(sub["n_samples"].sum())
        n_bins = int(sub["cte_n_bins"].sum())
        yaw_mean = float(sub["yaw_sum_signed"].sum() / n) if n > 0 else float("nan")
        yaw_var  = float(sub["yaw_sum_sq"].sum() / n - yaw_mean ** 2) if n > 0 else float("nan")
        yaw_var  = max(yaw_var, 0.0)
        yaw_rmse = math.sqrt(sub["yaw_sum_sq"].sum() / n) if n > 0 else float("nan")
        yaw_bias_fraction = (yaw_mean ** 2) / (yaw_mean ** 2 + yaw_var) if (yaw_mean ** 2 + yaw_var) > 0 else float("nan")
        schema = _resolve_schema(platform)
        per_platform[platform] = {
            "yaw_rate_rmse":     yaw_rmse,
            "yaw_residual_mean": yaw_mean,
            "yaw_residual_std":  math.sqrt(yaw_var),
            "yaw_bias_fraction": yaw_bias_fraction,
            "cte_rmse":          math.sqrt(sub["cte_sum_sq"].sum() / n_bins) if n_bins > 0 else float("nan"),
            "cte_signed_mean":   float(sub["cte_sum_signed"].sum() / n_bins) if n_bins > 0 else float("nan"),
            "n_segments":        int(len(sub)),
            "n_samples":         n,
            "truth_col":         schema["truth_col"],
            "schema_note":       schema.get("note"),
        }

    # ---- Per-regime ----
    per_regime = {}
    for k, acc in regime_acc.items():
        n = acc["n"]
        if n > 0:
            mean = acc["sum_signed"] / n
            per_regime[k] = {
                "yaw_rate_rmse":     math.sqrt(acc["sum_sq"] / n),
                "yaw_residual_mean": mean,
                "n_samples":         n,
            }
        else:
            per_regime[k] = {"yaw_rate_rmse": float("nan"), "yaw_residual_mean": float("nan"), "n_samples": 0}

    # ---- Per-route pooled ----
    route_rows = []
    for (platform, route), sub in seg.groupby(["platform", "route"]):
        n      = int(sub["n_samples"].sum())
        n_bins = int(sub["cte_n_bins"].sum())
        route_rows.append({
            "platform":         platform,
            "route":            route,
            "n_segments":       int(len(sub)),
            "total_distance_m": float(sub["distance_m"].sum()),
            "yaw_rate_rmse":    math.sqrt(sub["yaw_sum_sq"].sum() / n) if n > 0 else float("nan"),
            "cte_rmse":         math.sqrt(sub["cte_sum_sq"].sum() / n_bins) if n_bins > 0 else float("nan"),
            "cte_signed_mean":  float(sub["cte_sum_signed"].sum() / n_bins) if n_bins > 0 else float("nan"),
        })
    per_route = pd.DataFrame(route_rows).sort_values("cte_rmse", ascending=False).reset_index(drop=True)

    # ---- Worst-N tables (drop the internal sum columns from the view) ----
    view_cols = [
        "segment_path", "platform", "route", "idx", "n_samples", "distance_m",
        "yaw_rate_rmse", "yaw_residual_mean", "yaw_residual_std",
        "cte_rmse", "cte_signed_mean", "cte_abs_mean", "end_drift_m",
    ]
    worst_cte = seg.nlargest(top_n, "cte_rmse")[view_cols].to_dict("records")
    worst_yaw = seg.nlargest(top_n, "yaw_rate_rmse")[view_cols].to_dict("records")

    # ---- Distribution stats ----
    yaw_dist = _describe(seg["yaw_rate_rmse"])
    cte_dist = _describe(seg["cte_rmse"])

    # Drop internal cumulative columns from the public per_segment view.
    per_segment_public = seg[view_cols].copy()

    # ---- Bias check — computed here so the summary doesn't have to ----
    bias = bias_warnings(per_platform)

    return {
        "yaw_rate_rmse":           overall_yaw_rmse,
        "cte_rmse":                overall_cte_rmse,
        "n_segments":              int(len(seg)),
        "n_samples":               int(seg["n_samples"].sum()),
        "failed_segments":         failed,
        "failed_by_platform":      failed_by_platform,
        "platforms_seen":          platforms_seen,
        "per_platform":            per_platform,
        "per_regime":              per_regime,
        "per_segment":             per_segment_public,
        "per_route":               per_route,
        "worst_segments_by_cte":   worst_cte,
        "worst_segments_by_yaw":   worst_yaw,
        "yaw_rmse_distribution":   yaw_dist,
        "cte_rmse_distribution":   cte_dist,
        "bias_warnings":           bias,
    }


# ---------------------------------------------------------------------------
# Bias warnings — a small, programmatic view of which platforms have a
# systematic offset large enough to dominate CTE. Returned inside the score
# result and rendered at the top of `format_summary()`.
# ---------------------------------------------------------------------------

def bias_warnings(
    per_platform: dict,
    yaw_threshold_rad_s: float = YAW_BIAS_WARN_RAD_S,
    cte_threshold_m: float = CTE_DRIFT_WARN_M,
) -> list[dict]:
    """Return a list of (platform, metric, value, severity) entries.

    Severity is one of:
      - "ok":      |bias| ≤ threshold
      - "warn":    threshold < |bias| ≤ 3× threshold
      - "high":    |bias| > 3× threshold

    A platform appears at most twice (once for yaw bias, once for CTE drift).
    Only entries with severity != "ok" are returned; if the list is empty,
    nothing is systematically biased above the thresholds.
    """
    out: list[dict] = []
    for plat, m in per_platform.items():
        y = m.get("yaw_residual_mean", float("nan"))
        c = m.get("cte_signed_mean",   float("nan"))
        if y == y and abs(y) > yaw_threshold_rad_s:  # NaN-safe
            sev = "high" if abs(y) > 3 * yaw_threshold_rad_s else "warn"
            out.append({"platform": plat, "metric": "yaw_residual_mean",
                        "value": y, "threshold": yaw_threshold_rad_s, "severity": sev})
        if c == c and abs(c) > cte_threshold_m:
            sev = "high" if abs(c) > 3 * cte_threshold_m else "warn"
            out.append({"platform": plat, "metric": "cte_signed_mean",
                        "value": c, "threshold": cte_threshold_m, "severity": sev})
    return out


# ---------------------------------------------------------------------------
# Display helper — one-shot dashboard the agent can print
# ---------------------------------------------------------------------------

def format_summary(result: dict, top_n: int = 5) -> str:
    """Render a markdown dashboard of every view in `result`. Print this."""
    if result["n_segments"] == 0:
        plat_breakdown = ", ".join(
            f"{p}={n}" for p, n in (result.get("failed_by_platform") or {}).items()
        ) or "(no platforms encountered)"
        return (
            f"score-model: no segments scored ({result['failed_segments']} failed).\n"
            f"  failures by platform: {plat_breakdown}\n"
            f"  hint: check that PLATFORM_SCHEMA covers every platform you fed in, "
            f"that the resolved truth column exists in sim.csv, and that "
            f"predict_fn returns a DataFrame with `yaw_rate_pred_rads` of the right length."
        )

    L = []
    L.append("## score-model summary")
    L.append(f"- n_segments: {result['n_segments']} (failed: {result['failed_segments']}), n_samples: {result['n_samples']:,}")
    L.append(f"- **yaw_rate_rmse**: {result['yaw_rate_rmse']:.6f} rad/s")
    L.append(f"- **cte_rmse**: {result['cte_rmse']:.4f} m")

    # ---- 🚨 BIAS CHECK — top of the dashboard so it's hard to miss. ----
    L.append("")
    L.append("### 🚨 signed-bias check — read this BEFORE you ship")
    L.append("CTE is a double-integral of yaw error and is dominated by *systematic* bias, not RMS noise. "
             "If a row below is flagged, fit that calibration — don't tune yaw RMSE harder.")
    L.append("")
    L.append("| platform | yaw_bias (rad/s) | yaw bias_frac | cte_drift (m) | flag |")
    L.append("|---|---|---|---|---|")
    warn_lookup: dict[tuple[str, str], str] = {
        (w["platform"], w["metric"]): w["severity"]
        for w in result.get("bias_warnings", [])
    }
    for plat, m in result["per_platform"].items():
        yb  = m["yaw_residual_mean"]
        bf  = m["yaw_bias_fraction"]
        cd  = m["cte_signed_mean"]
        sev_y = warn_lookup.get((plat, "yaw_residual_mean"))
        sev_c = warn_lookup.get((plat, "cte_signed_mean"))
        flag_parts = []
        if sev_y:
            flag_parts.append(f"yaw_bias {'🚨' if sev_y == 'high' else '⚠️'}")
        if sev_c:
            flag_parts.append(f"cte_drift {'🚨' if sev_c == 'high' else '⚠️'}")
        flag = ", ".join(flag_parts) if flag_parts else "ok"
        L.append(f"| `{plat}` | {yb:+.5f} | {bf:.2f} | {cd:+.3f} | {flag} |")
    L.append("")
    L.append("Thresholds: yaw_bias |·| > "
             f"{YAW_BIAS_WARN_RAD_S} rad/s, cte_drift |·| > {CTE_DRIFT_WARN_M} m. "
             "'⚠️' = above threshold; '🚨' = above 3× threshold.")

    # ---- Per-platform RMSE table ----
    L.append("")
    L.append("### per platform")
    L.append("| platform | truth_col | yaw_rmse | yaw_std | cte_rmse | n_seg |")
    L.append("|---|---|---|---|---|---|")
    for plat, m in result["per_platform"].items():
        L.append(f"| `{plat}` | `{m['truth_col']}` | {m['yaw_rate_rmse']:.5f} | "
                 f"{m['yaw_residual_std']:.5f} | {m['cte_rmse']:.3f} | {m['n_segments']} |")
    # Schema notes (e.g. Tesla caveat) — printed once per platform that has one.
    notes = [(plat, m["schema_note"]) for plat, m in result["per_platform"].items() if m.get("schema_note")]
    if notes:
        L.append("")
        L.append("**Schema notes:**")
        for plat, n in notes:
            L.append(f"- `{plat}`: {n}")

    L.append("")
    L.append("### per regime (yaw only)")
    for k, m in result["per_regime"].items():
        L.append(f"- `{k}`: rmse={m['yaw_rate_rmse']:.5f}, bias={m['yaw_residual_mean']:+.5f}, n={m['n_samples']:,}")
    L.append("")
    L.append("### per-segment distribution")
    for label, dist in (("yaw_rate_rmse", result["yaw_rmse_distribution"]),
                        ("cte_rmse",      result["cte_rmse_distribution"])):
        L.append(f"- **{label}**: min={dist['min']:.5g}, p25={dist['p25']:.5g}, median={dist['median']:.5g}, mean={dist['mean']:.5g}, p75={dist['p75']:.5g}, max={dist['max']:.5g}, std={dist['std']:.5g}")
    L.append("")
    L.append(f"### top {top_n} worst segments by CTE")
    L.append("| route/idx | platform | dist_m | cte_rmse | cte_signed | yaw_rmse |")
    L.append("|---|---|---|---|---|---|")
    for r in result["worst_segments_by_cte"][:top_n]:
        L.append(f"| `{r['route']}/{r['idx']}` | `{r['platform']}` | {r['distance_m']:.0f} | {r['cte_rmse']:.2f} | {r['cte_signed_mean']:+.2f} | {r['yaw_rate_rmse']:.5f} |")
    L.append("")
    L.append(f"### top {top_n} worst segments by yaw")
    L.append("| route/idx | platform | n_samp | yaw_rmse | yaw_bias |")
    L.append("|---|---|---|---|---|")
    for r in result["worst_segments_by_yaw"][:top_n]:
        L.append(f"| `{r['route']}` `{r['idx']}` | `{r['platform']}` | {r['n_samples']} | {r['yaw_rate_rmse']:.5f} | {r['yaw_residual_mean']:+.5f} |")
    L.append("")
    L.append(f"### top {min(top_n, len(result['per_route']))} routes by CTE")
    L.append("| route | platform | n_seg | dist_m | yaw_rmse | cte_rmse | cte_signed |")
    L.append("|---|---|---|---|---|---|---|")
    for _, r in result["per_route"].head(top_n).iterrows():
        L.append(f"| `{r['route']}` | `{r['platform']}` | {r['n_segments']} | {r['total_distance_m']:.0f} | {r['yaw_rate_rmse']:.5f} | {r['cte_rmse']:.3f} | {r['cte_signed_mean']:+.3f} |")

    # Failure breakdown — if anything failed, surface where so the agent
    # doesn't have to guess.
    if result["failed_segments"] > 0:
        L.append("")
        L.append("### failures")
        for plat, n in (result.get("failed_by_platform") or {}).items():
            L.append(f"- `{plat}`: {n} failed (truth col missing? predict raised? wrong shape?)")

    return "\n".join(L)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _describe(s: pd.Series) -> dict:
    s = s.dropna()
    if len(s) == 0:
        return {"count": 0, "min": float("nan"), "p25": float("nan"), "median": float("nan"),
                "mean": float("nan"), "p75": float("nan"), "max": float("nan"), "std": float("nan")}
    return {
        "count":  int(len(s)),
        "min":    float(s.min()),
        "p25":    float(s.quantile(0.25)),
        "median": float(s.median()),
        "mean":   float(s.mean()),
        "p75":    float(s.quantile(0.75)),
        "max":    float(s.max()),
        "std":    float(s.std(ddof=0)),
    }


def _empty_result(
    failed: int,
    failed_by_platform: dict[str, int] | None = None,
    platforms_seen: dict[str, dict] | None = None,
) -> dict:
    return {
        "yaw_rate_rmse": float("nan"),
        "cte_rmse": float("nan"),
        "n_segments": 0,
        "n_samples": 0,
        "failed_segments": failed,
        "failed_by_platform": failed_by_platform or {},
        "platforms_seen": platforms_seen or {},
        "per_platform": {},
        "per_regime": {},
        "per_segment": pd.DataFrame(),
        "per_route": pd.DataFrame(),
        "worst_segments_by_cte": [],
        "worst_segments_by_yaw": [],
        "yaw_rmse_distribution": _describe(pd.Series(dtype=float)),
        "cte_rmse_distribution": _describe(pd.Series(dtype=float)),
        "bias_warnings": [],
    }


__all__ = [
    "score",
    "format_summary",
    "bias_warnings",
    "integrate_trajectory",
    "PLATFORM_SCHEMA",
    "ALLOWED_INPUT_COLUMNS",
    "YAW_BIAS_WARN_RAD_S",
    "CTE_DRIFT_WARN_M",
]
