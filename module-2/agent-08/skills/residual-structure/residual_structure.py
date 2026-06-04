"""residual-structure — diagnose what's LEFT in your residual after a fit.

A well-fitted understeer model leaves an ~white residual that scales with
sensor noise. A model that's missing a term leaves a residual with
*structure*: temporal autocorrelation (you need a dynamic / lag term),
correlation with a feature derivative (you need a rate term), or
asymmetry by sign of steering (you need an odd-power / hysteresis term).

The v2 cohort hit a yaw ceiling at ~+48% because almost everyone stopped
at V1 understeer (`v·δ / (L + K_us·v²)`) and shipped. The single winner
(m2-agent-05, +51.5%) saw that the V1 residual was autocorrelated and
added a steering-rate lead `τ·δ̇` — τ converged to **-60 ms** on every
platform, a real sensor-pipeline delay. This skill exposes that signal
so the agent doesn't have to discover it by hand.

The verdict is one of:
  - "noise_floor"        — residual passes all four structure checks. Stop.
  - "structure_detected" — at least one check fires; the reason names which.

Schema-aware via `scoring-model`'s `PLATFORM_SCHEMA`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Reuse the schema + allowlist from scoring-model.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "score-model"))
from score import (  # noqa: E402
    ALLOWED_INPUT_COLUMNS,
    DEFAULT_SCHEMA,
    PLATFORM_SCHEMA,
)


# ---------------------------------------------------------------------------
# Decision thresholds. Tunable; edit if your problem's noise scale differs.
# ---------------------------------------------------------------------------
ACF_NOISE_THRESHOLD       = 0.10   # |pooled ACF| at any lag > 0 above this → structure
XCORR_NOISE_THRESHOLD     = 0.10   # |pooled xcorr| with any feature/deriv above this → structure
ASYMMETRY_NOISE_THRESHOLD = 0.20   # odd_component_share above this → asymmetric residual
ASYMMETRY_MAGNITUDE_FLOOR = 0.10   # AND |mean+ - mean-| / residual_std must exceed this
                                   # (without this, pure noise samples a 1.0 odd share by chance)
DEFAULT_ACF_LAGS          = (1, 2, 5, 10, 20)
DEFAULT_FEATURES_TO_TEST  = ("v_mps", "delta_road_rad", "a_long_mps2", "yaw_rate_pred_rads")


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def _platform_from_path(p: Path) -> str:
    return p.resolve().parents[3].name


def _default_segment_paths() -> list[Path]:
    root = Path.cwd() / "data" / "sim" / "segments"
    if not root.exists():
        return []
    return sorted(p for p in root.glob("*/**/sim.csv") if p.is_file())


def _resolve_schema(platform: str) -> dict:
    return PLATFORM_SCHEMA.get(platform, DEFAULT_SCHEMA)


# ---------------------------------------------------------------------------
# Per-segment statistics. We compute weighted sums so the platform-level
# aggregation is a true sample-weighted pool, not a mean-of-means.
# ---------------------------------------------------------------------------

def _segment_stats(
    t: np.ndarray,
    v: np.ndarray,
    resid: np.ndarray,
    sim_df_agent: pd.DataFrame,
    sim_df_full: pd.DataFrame,
    features: tuple[str, ...],
    lags: tuple[int, ...],
    v_floor: float,
) -> dict | None:
    mask = v > v_floor
    if mask.sum() < max(lags) + 10:
        return None

    r = resid[mask].astype(float)
    n = len(r)
    r_mean = r.mean()
    r_var  = float(r.var(ddof=0))
    # Zero-variance residual = perfect prediction (Tesla V0 = truth).
    # That IS the noise floor; record an all-zero stats packet so the
    # platform aggregates to a clean noise_floor verdict instead of being
    # silently dropped.
    if r_var < 1e-18:
        return {
            "n":           n,
            "r_var":       0.0,
            "acf":         {lag: 0.0 for lag in lags},
            "feat_corrs":  {},
            "asym_share":  0.0,
            "asym_pos":    0.0,
            "asym_neg":    0.0,
        }

    # ---- Autocorrelation: r[t] vs r[t - lag], v-filtered indices ----
    # We compute on the v-filtered residual array directly. Lags refer to
    # samples; assumes uniform-ish sampling (the cohort's sims do).
    acf = {}
    rc = r - r_mean
    for lag in lags:
        if lag >= n:
            acf[lag] = float("nan"); continue
        num = float(np.sum(rc[lag:] * rc[:-lag]))
        den = float(np.sum(rc ** 2))
        acf[lag] = num / den if den > 0 else float("nan")

    # ---- Cross-correlations: residual vs each feature AND its time-derivative ----
    feat_corrs: dict[tuple[str, bool], float] = {}
    for feat in features:
        # Prefer the agent-view (matches what predict sees).
        if feat in sim_df_agent.columns:
            f = sim_df_agent[feat].to_numpy(dtype=float)
        elif feat in sim_df_full.columns:
            f = sim_df_full[feat].to_numpy(dtype=float)
        else:
            continue

        # Raw correlation.
        f_m = f[mask]
        if f_m.size and float(f_m.var(ddof=0)) > 1e-18:
            feat_corrs[(feat, False)] = _pearson(r, f_m)

        # Derivative correlation — d f / d t via np.gradient on the FULL
        # arrays (gradient at the boundary is one-sided; mask afterwards).
        if len(t) >= 2:
            f_dot = np.gradient(f, t)
            f_dot_m = f_dot[mask]
            if f_dot_m.size and float(f_dot_m.var(ddof=0)) > 1e-18:
                feat_corrs[(feat, True)] = _pearson(r, f_dot_m)

    # ---- Asymmetry: sign-of-steering decomposition.
    # If residual is purely even in delta, mean(residual | δ > 0) ≈
    # mean(residual | δ < 0). If purely odd, they're equal-and-opposite.
    # The "odd component share" is |mean+ - mean-| / (|mean+| + |mean-|).
    asym_share = float("nan")
    asym_pos   = float("nan")
    asym_neg   = float("nan")
    if "delta_road_rad" in sim_df_agent.columns:
        d = sim_df_agent["delta_road_rad"].to_numpy(dtype=float)[mask]
        # Ignore the ~straight band where δ is dominated by sensor zero.
        pos = d > 0.02
        neg = d < -0.02
        if pos.sum() > 50 and neg.sum() > 50:
            mp = float(r[pos].mean())
            mn = float(r[neg].mean())
            denom = abs(mp) + abs(mn)
            asym_share = abs(mp - mn) / denom if denom > 1e-12 else 0.0
            asym_pos   = mp
            asym_neg   = mn

    return {
        "n": n,
        "r_var": r_var,
        "acf": acf,
        "feat_corrs": feat_corrs,
        "asym_share": asym_share,
        "asym_pos":   asym_pos,
        "asym_neg":   asym_neg,
    }


def _pearson(x: np.ndarray, y: np.ndarray) -> float:
    """Pearson correlation, NaN-safe, returns 0 on degenerate inputs."""
    n = min(len(x), len(y))
    if n < 3:
        return 0.0
    x = x[:n]; y = y[:n]
    xm = x - x.mean()
    ym = y - y.mean()
    denom = float(np.sqrt(np.sum(xm ** 2) * np.sum(ym ** 2)))
    if denom < 1e-18:
        return 0.0
    return float(np.sum(xm * ym) / denom)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def residual_structure(
    predict_fn,
    segment_paths: list | None = None,
    platform_filter: str | None = None,
    sample_filter_v_mps: float = 2.0,
    features: tuple[str, ...] = DEFAULT_FEATURES_TO_TEST,
    lags: tuple[int, ...] = DEFAULT_ACF_LAGS,
) -> dict:
    """Characterise what's left in the residual after a fit.

    Args:
        predict_fn: callable(sim_df, platform) -> DataFrame with `yaw_rate_pred_rads`.
        segment_paths: list[Path] or None (default — all platforms).
        platform_filter: keep only this platform if set.
        sample_filter_v_mps: same v-filter as scoring-model.
        features: column names to test for residual correlation (raw AND first
            derivative). Default covers v, δ, a_long, and the V0 baseline.
        lags: ACF lags (in samples) to report. Default 1, 2, 5, 10, 20.

    Returns:
        dict with per_platform → {n_segments, n_samples, residual_std,
        acf, feature_correlations (list, sorted by |corr| desc),
        asymmetry, verdict, verdict_reason}, plus failed_segments.
    """
    if segment_paths is None:
        segment_paths = _default_segment_paths()
    paths = [Path(p) for p in segment_paths]
    if platform_filter is not None:
        paths = [p for p in paths if _platform_from_path(p) == platform_filter]

    # Per-segment buckets, keyed by platform.
    per_plat: dict[str, list[dict]] = {}
    failed = 0

    for p in paths:
        platform = _platform_from_path(p)
        schema = _resolve_schema(platform)
        truth_col = schema["truth_col"]
        base_col  = schema["baseline_col"]

        try:
            sim_df = pd.read_csv(p)
        except Exception:
            failed += 1; continue
        if any(c not in sim_df.columns for c in (truth_col, "v_mps", "t_s")):
            failed += 1; continue

        sim_df_agent = sim_df[[c for c in sim_df.columns if c in ALLOWED_INPUT_COLUMNS]].copy()
        if "yaw_rate_pred_rads" not in sim_df_agent.columns and base_col in sim_df.columns:
            sim_df_agent["yaw_rate_pred_rads"] = sim_df[base_col].astype(float).to_numpy()

        try:
            pred_df = predict_fn(sim_df_agent, platform)
        except Exception:
            failed += 1; continue
        if (
            not isinstance(pred_df, pd.DataFrame)
            or "yaw_rate_pred_rads" not in pred_df.columns
            or len(pred_df) != len(sim_df)
        ):
            failed += 1; continue

        t        = sim_df["t_s"].to_numpy(dtype=float)
        v        = sim_df["v_mps"].to_numpy(dtype=float)
        if len(t) < 2 or np.any(np.diff(t) <= 0):
            failed += 1; continue
        yr_truth = sim_df[truth_col].to_numpy(dtype=float)
        yr_pred  = pred_df["yaw_rate_pred_rads"].to_numpy(dtype=float)
        resid    = yr_pred - yr_truth

        stats = _segment_stats(t, v, resid, sim_df_agent, sim_df, features, lags, sample_filter_v_mps)
        if stats is None:
            failed += 1; continue
        per_plat.setdefault(platform, []).append(stats)

    # Pool per platform — sample-weighted means of each quantity.
    out: dict[str, dict] = {}
    for platform, bucket in per_plat.items():
        total_n = sum(s["n"] for s in bucket)
        if total_n == 0:
            continue

        # Pooled residual variance → std (for context).
        pooled_var = sum(s["n"] * s["r_var"] for s in bucket) / total_n
        residual_std = float(np.sqrt(pooled_var))

        # Pooled ACF: weighted mean.
        acf_pooled = {}
        for lag in lags:
            num = 0.0; den = 0
            for s in bucket:
                v = s["acf"].get(lag, float("nan"))
                if v == v:  # not NaN
                    num += s["n"] * v
                    den += s["n"]
            acf_pooled[lag] = (num / den) if den > 0 else float("nan")

        # Pooled feature/derivative correlations: weighted mean per key.
        key_set = set()
        for s in bucket:
            key_set.update(s["feat_corrs"].keys())
        feat_pooled: list[dict] = []
        for key in key_set:
            num = 0.0; den = 0
            for s in bucket:
                v = s["feat_corrs"].get(key)
                if v is not None and v == v:
                    num += s["n"] * v
                    den += s["n"]
            if den > 0:
                feat, is_deriv = key
                feat_pooled.append({
                    "feature":       feat,
                    "is_derivative": is_deriv,
                    "label":         f"d({feat})/dt" if is_deriv else feat,
                    "corr":          num / den,
                })
        feat_pooled.sort(key=lambda d: abs(d["corr"]), reverse=True)

        # Pooled asymmetry.
        valid_asym = [s for s in bucket if s["asym_share"] == s["asym_share"]]
        if valid_asym:
            asym_share = float(np.average(
                [s["asym_share"] for s in valid_asym],
                weights=[s["n"] for s in valid_asym],
            ))
            asym_pos = float(np.average(
                [s["asym_pos"] for s in valid_asym],
                weights=[s["n"] for s in valid_asym],
            ))
            asym_neg = float(np.average(
                [s["asym_neg"] for s in valid_asym],
                weights=[s["n"] for s in valid_asym],
            ))
        else:
            asym_share = float("nan")
            asym_pos = asym_neg = float("nan")

        # ---- Verdict.
        reasons: list[str] = []
        worst_acf_lag, worst_acf_val = max(
            ((lag, acf_pooled[lag]) for lag in lags if acf_pooled[lag] == acf_pooled[lag]),
            key=lambda kv: abs(kv[1]),
            default=(None, 0.0),
        )
        if worst_acf_lag is not None and abs(worst_acf_val) > ACF_NOISE_THRESHOLD:
            reasons.append(
                f"residual autocorrelated at lag {worst_acf_lag} samples "
                f"(ACF={worst_acf_val:+.2f}) → try a dynamic / lead-lag term "
                f"(e.g. + τ·d(δ)/dt)"
            )
        top_corr = feat_pooled[0] if feat_pooled else None
        if top_corr and abs(top_corr["corr"]) > XCORR_NOISE_THRESHOLD:
            kind = "feature derivative" if top_corr["is_derivative"] else "feature"
            reasons.append(
                f"residual correlates with {kind} `{top_corr['label']}` "
                f"(ρ={top_corr['corr']:+.2f}) → add a model term in that {kind}"
            )
        # Asymmetry must be BOTH a high odd-share AND large relative to noise.
        # Without the magnitude floor, pure-noise residuals occasionally show a
        # 1.0 odd share by chance (when both bin means randomly land on
        # opposite signs near zero).
        asym_mag = (abs(asym_pos - asym_neg) / residual_std) if (residual_std > 1e-18 and asym_pos == asym_pos) else 0.0
        if (
            asym_share == asym_share
            and asym_share > ASYMMETRY_NOISE_THRESHOLD
            and asym_mag > ASYMMETRY_MAGNITUDE_FLOOR
        ):
            reasons.append(
                f"residual is sign-asymmetric in δ "
                f"(mean+={asym_pos:+.5f}, mean-={asym_neg:+.5f}, odd share={asym_share:.2f}, "
                f"|Δ|/σ={asym_mag:.2f}) → try a cubic (α3·δ³) or sign-of-δ̇ hysteresis term"
            )

        verdict = "structure_detected" if reasons else "noise_floor"
        verdict_reason = "; ".join(reasons) if reasons else (
            "no autocorrelation, feature correlation, or sign-asymmetry above thresholds — "
            "you are at the noise floor for this model class."
        )

        out[platform] = {
            "n_segments":            len(bucket),
            "n_samples":             total_n,
            "residual_std":          residual_std,
            "acf":                   acf_pooled,
            "feature_correlations":  feat_pooled,
            "asymmetry": {
                "mean_residual_pos_delta": asym_pos,
                "mean_residual_neg_delta": asym_neg,
                "odd_component_share":     asym_share,
            },
            "verdict":               verdict,
            "verdict_reason":        verdict_reason,
        }

    return {
        "per_platform":    out,
        "failed_segments": failed,
        "lags":            list(lags),
    }


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

def format_residual_structure_summary(result: dict, top_n_features: int = 5) -> str:
    """Render the verdict block first (it's the answer), then the supporting
    numbers per platform."""
    if not result["per_platform"]:
        return f"residual-structure: no platforms scored ({result['failed_segments']} segments failed)."

    L = []
    L.append("## residual-structure diagnostic")
    L.append("")
    L.append("### 🎯 verdicts — read this first")
    L.append("")
    L.append("| platform | residual_std | verdict | reason |")
    L.append("|---|---|---|---|")
    for plat, m in result["per_platform"].items():
        icon = "✅" if m["verdict"] == "noise_floor" else "🔎"
        L.append(f"| `{plat}` | {m['residual_std']:.5f} | {icon} {m['verdict']} | {m['verdict_reason']} |")
    L.append("")
    L.append(
        f"Thresholds: |ACF| > {ACF_NOISE_THRESHOLD} at any lag > 0, "
        f"|feature corr| > {XCORR_NOISE_THRESHOLD}, "
        f"asymmetry share > {ASYMMETRY_NOISE_THRESHOLD} AND "
        f"|Δ|/σ > {ASYMMETRY_MAGNITUDE_FLOOR}. "
        "Anything *above* a threshold means there's structure your model isn't capturing."
    )

    for plat, m in result["per_platform"].items():
        L.append("")
        L.append(f"### `{plat}` — supporting detail")
        # ACF table.
        L.append("")
        L.append("**Autocorrelation** (residual vs itself, shifted by lag samples):")
        L.append("")
        L.append("| lag | ACF |")
        L.append("|---|---|")
        for lag, val in m["acf"].items():
            flag = " ⚠️" if val == val and abs(val) > ACF_NOISE_THRESHOLD else ""
            L.append(f"| {lag} | {val:+.3f}{flag} |")
        # Feature correlations.
        L.append("")
        L.append("**Feature correlations** (ranked by |ρ|):")
        L.append("")
        L.append("| feature | derivative? | ρ |")
        L.append("|---|---|---|")
        for row in m["feature_correlations"][:top_n_features]:
            flag = " ⚠️" if abs(row["corr"]) > XCORR_NOISE_THRESHOLD else ""
            L.append(f"| `{row['feature']}` | {'yes' if row['is_derivative'] else 'no'} | {row['corr']:+.3f}{flag} |")
        # Asymmetry.
        a = m["asymmetry"]
        if a["odd_component_share"] == a["odd_component_share"]:
            flag = " ⚠️" if a["odd_component_share"] > ASYMMETRY_NOISE_THRESHOLD else ""
            L.append("")
            L.append(
                f"**Asymmetry in δ:** mean(resid | δ>+0.02)={a['mean_residual_pos_delta']:+.5f}, "
                f"mean(resid | δ<-0.02)={a['mean_residual_neg_delta']:+.5f}, "
                f"odd-component share={a['odd_component_share']:.2f}{flag}"
            )

    return "\n".join(L)


__all__ = [
    "residual_structure",
    "format_residual_structure_summary",
    "ACF_NOISE_THRESHOLD",
    "XCORR_NOISE_THRESHOLD",
    "ASYMMETRY_NOISE_THRESHOLD",
    "ASYMMETRY_MAGNITUDE_FLOOR",
    "DEFAULT_ACF_LAGS",
    "DEFAULT_FEATURES_TO_TEST",
]
