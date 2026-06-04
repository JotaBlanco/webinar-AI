"""Fit per-platform bias + ridge residual head on V1; score yaw & CTE.

Reads training data from data/sim/segments (truth available).
Reads inputs from data/sim-only/segments (the contract for grading).

For each platform:
  - Build V1 prediction (V1 is platform-aware; Tesla falls through to V0 passthrough).
  - Fit:
      a) per-platform additive bias `b` (single scalar).
      b) ridge residual head: residual = truth - (V1 + b), features
         [delta_road_rad, delta_road_rad*v, v, a_long, abs(delta), delta*|delta|*v].
  - Combined predict: V1 + b + ridge(features).
Then score yaw-rate RMSE and CTE RMSE pooled across all platforms.

We exclude HYUNDAI_IONIQ_5 from training only if we want — but here we include it.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-03")
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "_shared"))

from v1_baseline import predict_v1  # noqa: E402
from traj_metrics import cte_rmse_segment  # noqa: E402

SIM_DIR = ROOT / "data" / "sim" / "segments"
SIM_ONLY_DIR = ROOT / "data" / "sim-only" / "segments"

TRUTH_COL_BY_PLATFORM = {
    "TESLA_MODEL_3": "psi_dot_rads",
    "FORD_F_150_LIGHTNING_MK1": "yaw_rate_meas_rads",
    "FORD_MUSTANG_MACH_E_MK1": "yaw_rate_meas_rads",
    "HYUNDAI_IONIQ_5": "yaw_rate_meas_rads",
}

SIM_ONLY_COLS = [
    "t_s", "delta_wheel_deg", "delta_road_rad", "v_mps",
    "a_long_mps2", "accel_pedal_pct", "brake_pressed",
    "yaw_rate_pred_rads",
]


def find_sim_csvs(platform_dir: Path):
    return sorted(platform_dir.rglob("sim.csv"))


def to_sim_only_df(df: pd.DataFrame) -> pd.DataFrame:
    """Project a sim/ DataFrame down to the 8-col contract."""
    out = pd.DataFrame(index=df.index)
    for c in SIM_ONLY_COLS:
        if c in df.columns:
            out[c] = df[c]
        elif c == "brake_pressed" and "brake_pedal_state" in df.columns:
            # Tesla schema uses brake_pedal_state; cast >0 → 1
            out[c] = (df["brake_pedal_state"].astype(float) > 0).astype(int)
        elif c == "yaw_rate_pred_rads":
            out[c] = df["yaw_rate_pred_rads"]
        else:
            out[c] = 0.0
    return out


def build_features(sim_df: pd.DataFrame) -> np.ndarray:
    d = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    a = sim_df["a_long_mps2"].to_numpy()
    feats = np.column_stack([
        d,
        d * v,
        v,
        a,
        np.abs(d),
        d * np.abs(d) * v,
    ])
    return feats


def load_platform_segments(platform: str, root: Path):
    pdir = root / platform
    paths = find_sim_csvs(pdir)
    segs = []
    for p in paths:
        df = pd.read_csv(p)
        segs.append((p, df))
    return segs


def load_platform_paired(platform: str):
    """Pair sim-only (input) with sim (truth) by relative path."""
    truth_col = TRUTH_COL_BY_PLATFORM[platform]
    sim_only_root = SIM_ONLY_DIR / platform
    sim_root = SIM_DIR / platform
    paths = sorted(sim_only_root.rglob("sim.csv"))
    paired = []
    for p in paths:
        rel = p.relative_to(sim_only_root)
        sim_path = sim_root / rel
        if not sim_path.exists():
            continue
        try:
            df_in = pd.read_csv(p)
            df_truth = pd.read_csv(sim_path)
        except Exception:
            continue
        if truth_col not in df_truth.columns:
            continue
        if len(df_in) != len(df_truth):
            continue
        df_in = df_in.copy()
        df_in["_truth"] = df_truth[truth_col].to_numpy()
        paired.append((p, df_in))
    return paired


def fit_platform(platform: str, paired):
    # paired: list of (path, df_in) where df_in has _truth column
    feat_list = []
    resid_list = []
    for path, df in paired:
        sim_only = df[SIM_ONLY_COLS].copy()
        yp = predict_v1(sim_only, platform)["yaw_rate_pred_rads"].to_numpy()
        yt = df["_truth"].to_numpy()
        feats = build_features(sim_only)
        feat_list.append(feats)
        resid_list.append(yt - yp)
    if not feat_list:
        return {"bias": 0.0, "ridge_w": [0.0] * 6, "lambda": 0.0}
    X = np.concatenate(feat_list, axis=0)
    r = np.concatenate(resid_list, axis=0)
    # Bias = mean residual
    bias = float(np.mean(r))
    r_after_bias = r - bias
    # Ridge regression on features with L2
    # Standardize features
    mu = X.mean(axis=0)
    sigma = X.std(axis=0) + 1e-9
    Xs = (X - mu) / sigma
    lam = 1e3  # ridge strength
    A = Xs.T @ Xs + lam * np.eye(Xs.shape[1])
    b = Xs.T @ r_after_bias
    w_s = np.linalg.solve(A, b)
    # Convert back to original-scale weights (drop intercept term, absorbed in bias)
    w = w_s / sigma
    intercept_adj = -float(np.sum(w * mu))
    return {
        "bias": bias + intercept_adj,
        "ridge_w": w.tolist(),
        "lambda": lam,
        "feat_mu": mu.tolist(),
        "feat_sigma": sigma.tolist(),
    }


def predict_with_coeffs(sim_only_df: pd.DataFrame, platform: str, coeffs: dict) -> np.ndarray:
    yp = predict_v1(sim_only_df, platform)["yaw_rate_pred_rads"].to_numpy()
    if platform not in coeffs:
        return yp
    c = coeffs[platform]
    bias = float(c.get("bias", 0.0))
    w = np.array(c.get("ridge_w", [0.0] * 6), dtype=float)
    feats = build_features(sim_only_df)
    correction = bias + feats @ w
    return yp + correction


def _score_with_pred_fn(pred_fn, paired_by_platform):
    yaw_sq_sum = 0.0
    yaw_n = 0
    cte_sq_sum = 0.0
    cte_n = 0
    per_platform = {}
    for platform, paired in paired_by_platform.items():
        p_yaw_sq = 0.0
        p_yaw_n = 0
        p_cte_sq = 0.0
        p_cte_n = 0
        for path, df in paired:
            sim_only = df[SIM_ONLY_COLS].copy()
            yp = pred_fn(sim_only, platform)
            yt = df["_truth"].to_numpy()
            t = df["t_s"].to_numpy()
            v = df["v_mps"].to_numpy()
            res = yp - yt
            p_yaw_sq += float(np.sum(res * res))
            p_yaw_n += int(len(res))
            sum_sq, n_bins, _ = cte_rmse_segment(t, v, yt, yp)
            p_cte_sq += sum_sq
            p_cte_n += n_bins
        per_platform[platform] = {
            "yaw_rmse": math.sqrt(p_yaw_sq / p_yaw_n) if p_yaw_n else None,
            "cte_rmse_m": math.sqrt(p_cte_sq / p_cte_n) if p_cte_n else None,
            "n_samples": p_yaw_n,
            "n_bins": p_cte_n,
        }
        yaw_sq_sum += p_yaw_sq
        yaw_n += p_yaw_n
        cte_sq_sum += p_cte_sq
        cte_n += p_cte_n
    return {
        "pooled_yaw_rmse": math.sqrt(yaw_sq_sum / yaw_n) if yaw_n else None,
        "pooled_cte_rmse_m": math.sqrt(cte_sq_sum / cte_n) if cte_n else None,
        "per_platform": per_platform,
    }


def score_v0(paired_by_platform):
    return _score_with_pred_fn(
        lambda sim_only, plat: sim_only["yaw_rate_pred_rads"].to_numpy(),
        paired_by_platform,
    )


def score_v1(paired_by_platform):
    return _score_with_pred_fn(
        lambda sim_only, plat: predict_v1(sim_only, plat)["yaw_rate_pred_rads"].to_numpy(),
        paired_by_platform,
    )


def score_final(coeffs, paired_by_platform):
    return _score_with_pred_fn(
        lambda sim_only, plat: predict_with_coeffs(sim_only, plat, coeffs),
        paired_by_platform,
    )


def main():
    print("Pairing sim-only inputs with sim truth per platform...")
    paired_by_platform = {}
    for platform in TRUTH_COL_BY_PLATFORM:
        paired = load_platform_paired(platform)
        print(f"  {platform}: {len(paired)} paired segments")
        paired_by_platform[platform] = paired

    print("\nFitting per-platform bias + ridge residual head...")
    coeffs = {}
    for platform, paired in paired_by_platform.items():
        coeffs[platform] = fit_platform(platform, paired)
        print(f"  {platform}: bias={coeffs[platform]['bias']:.6f}")
        print(f"    ridge_w={[f'{w:.4f}' for w in coeffs[platform]['ridge_w']]}")

    out_coeffs_path = ROOT / "out" / "coeffs.json"
    with open(out_coeffs_path, "w") as fh:
        json.dump(coeffs, fh, indent=2)
    print(f"Wrote {out_coeffs_path}")

    print("\nScoring V0 baseline...")
    v0 = score_v0(paired_by_platform)
    print(json.dumps(v0, indent=2))

    print("\nScoring V1 baseline (no corrections, Tesla=V0 passthrough)...")
    v1 = score_v1(paired_by_platform)
    print(json.dumps(v1, indent=2))

    print("\nScoring V1 + bias + ridge residual head (FINAL)...")
    fit = score_final(coeffs, paired_by_platform)
    print(json.dumps(fit, indent=2))

    def pct(new, old):
        if old is None or new is None:
            return None
        return 100.0 * (old - new) / old

    print("\n=== HEADLINES (pooled) ===")
    print(f"V0 yaw RMSE: {v0['pooled_yaw_rmse']:.6f}, CTE: {v0['pooled_cte_rmse_m']:.4f}")
    print(f"V1 yaw RMSE: {v1['pooled_yaw_rmse']:.6f}, CTE: {v1['pooled_cte_rmse_m']:.4f}  "
          f"(yaw {pct(v1['pooled_yaw_rmse'], v0['pooled_yaw_rmse']):.1f}%, "
          f"CTE {pct(v1['pooled_cte_rmse_m'], v0['pooled_cte_rmse_m']):.1f}%)")
    print(f"FINAL yaw RMSE: {fit['pooled_yaw_rmse']:.6f}, CTE: {fit['pooled_cte_rmse_m']:.4f}  "
          f"(yaw {pct(fit['pooled_yaw_rmse'], v0['pooled_yaw_rmse']):.1f}%, "
          f"CTE {pct(fit['pooled_cte_rmse_m'], v0['pooled_cte_rmse_m']):.1f}%)")

    summary = {"v0": v0, "v1": v1, "final": fit, "coeffs": coeffs}
    with open(ROOT / "out" / "scores.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"\nWrote {ROOT / 'out' / 'scores.json'}")


if __name__ == "__main__":
    main()
