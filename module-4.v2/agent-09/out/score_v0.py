"""Score the V0 baseline (yaw_rate_pred_rads in sim.csv) across all platforms.

Also fits per-platform understeer-gradient corrections:
    yaw_rate = v * delta_road / (L + K_us * v^2)
and produces both yaw RMSE and CTE RMSE.
"""
from __future__ import annotations
import sys
from pathlib import Path
import math
import json
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-09")
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "code"))
from traj_metrics import cte_rmse_segment  # noqa

SIM_ROOT = ROOT / "data" / "sim" / "segments"

# Per-platform wheelbase (m) — from parameters.py + reasonable IONIQ_5 default
L_BY_PLATFORM = {
    "TESLA_MODEL_3":              2.875,
    "FORD_MUSTANG_MACH_E_MK1":    2.984,
    "FORD_F_150_LIGHTNING_MK1":   3.70,
    "HYUNDAI_IONIQ_5":            3.00,   # spec: 3000 mm
}


def load_segment(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    # Normalise truth column: Tesla uses psi_dot_rads, others use yaw_rate_meas_rads
    if "yaw_rate_meas_rads" not in df.columns and "psi_dot_rads" in df.columns:
        df["yaw_rate_meas_rads"] = df["psi_dot_rads"]
    # Tesla legacy CSVs don't carry a pre-computed yaw_rate_pred_rads — compute KS proxy
    if "yaw_rate_pred_rads" not in df.columns:
        v = df["v_mps"].to_numpy()
        d = df["delta_road_rad"].to_numpy()
        L = 2.875  # Tesla default; caller can override
        df["yaw_rate_pred_rads"] = v * d / L
    return df


def yaw_rmse(yr_truth: np.ndarray, yr_pred: np.ndarray) -> tuple[float, int]:
    err = yr_truth - yr_pred
    return float(np.sum(err * err)), int(len(err))


def gather_segments(platform: str, limit: int | None = None) -> list[Path]:
    paths = sorted((SIM_ROOT / platform).rglob("sim.csv"))
    if limit:
        paths = paths[:limit]
    return paths


def score_predictor(platform: str, predictor, limit: int | None = None,
                    verbose: bool = False) -> dict:
    paths = gather_segments(platform, limit=limit)
    yaw_sq = 0.0
    yaw_n = 0
    cte_sq = 0.0
    cte_n = 0
    cte_total_dist = 0.0
    n_seg = 0
    for p in paths:
        try:
            df = load_segment(p)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        t = df["t_s"].to_numpy()
        v = df["v_mps"].to_numpy()
        yr_truth = df["yaw_rate_meas_rads"].to_numpy()
        try:
            yr_pred = predictor(df, platform)
        except Exception as e:
            if verbose:
                print(f"  fail on {p}: {e}")
            continue
        yr_pred = np.asarray(yr_pred)
        # finite mask
        mask = np.isfinite(yr_truth) & np.isfinite(yr_pred) & np.isfinite(v)
        if mask.sum() < 10:
            continue
        sse, n = yaw_rmse(yr_truth[mask], yr_pred[mask])
        yaw_sq += sse
        yaw_n += n

        sum_sq, n_bins, total = cte_rmse_segment(t, v, yr_truth, yr_pred,
                                                  grid_step_m=1.0,
                                                  min_distance_m=20.0)
        cte_sq += sum_sq
        cte_n += n_bins
        cte_total_dist += total
        n_seg += 1

    yaw_r = math.sqrt(yaw_sq / yaw_n) if yaw_n > 0 else float("nan")
    cte_r = math.sqrt(cte_sq / cte_n) if cte_n > 0 else float("nan")
    return {
        "platform": platform,
        "n_segments": n_seg,
        "yaw_rmse_rads": yaw_r,
        "cte_rmse_m": cte_r,
        "yaw_samples": yaw_n,
        "cte_bins": cte_n,
        "total_distance_m": cte_total_dist,
    }


# --- predictors -------------------------------------------------------------

def pred_v0(df, platform):
    return df["yaw_rate_pred_rads"].to_numpy()


def pred_understeer(K_us: float, scale: float, L: float):
    def _p(df, platform):
        v = df["v_mps"].to_numpy()
        d = df["delta_road_rad"].to_numpy() * scale
        return v * d / (L + K_us * v * v)
    return _p


def fit_understeer(platform: str, limit: int | None = None) -> tuple[float, float]:
    """Fit (K_us, scale) per platform on yaw RMSE."""
    from scipy.optimize import minimize
    paths = gather_segments(platform, limit=limit)
    # Pre-collect arrays
    chunks = []
    for p in paths:
        df = load_segment(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        v = df["v_mps"].to_numpy()
        d = df["delta_road_rad"].to_numpy()
        yr_truth = df["yaw_rate_meas_rads"].to_numpy()
        mask = np.isfinite(v) & np.isfinite(d) & np.isfinite(yr_truth) & (v > 1.0)
        if mask.sum() < 50:
            continue
        chunks.append((v[mask], d[mask], yr_truth[mask]))
    L = L_BY_PLATFORM[platform]

    def loss(x):
        K_us, scale = x
        sse = 0.0
        n = 0
        for v, d, yr in chunks:
            yr_p = v * d * scale / (L + K_us * v * v)
            e = yr - yr_p
            sse += float(np.sum(e * e))
            n += len(e)
        return math.sqrt(sse / n)

    x0 = [0.0, 1.0]
    res = minimize(loss, x0, method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-7, "maxiter": 400})
    K_us, scale = res.x
    return K_us, scale, res.fun


def main():
    results = {"v0": {}, "understeer": {}, "coeffs": {}}
    for plat in L_BY_PLATFORM:
        print(f"=== {plat} ===")
        v0 = score_predictor(plat, pred_v0)
        print(f"V0:  yaw_rmse={v0['yaw_rmse_rads']:.5f}  cte_rmse={v0['cte_rmse_m']:.3f} m  (n_seg={v0['n_segments']})")
        results["v0"][plat] = v0

        K_us, scale, loss = fit_understeer(plat)
        print(f"  fit K_us={K_us:.6f}  scale={scale:.4f}  train_loss={loss:.5f}")
        results["coeffs"][plat] = {"K_us": K_us, "scale": scale, "L": L_BY_PLATFORM[plat]}

        us = score_predictor(plat, pred_understeer(K_us, scale, L_BY_PLATFORM[plat]))
        print(f"US:  yaw_rmse={us['yaw_rmse_rads']:.5f}  cte_rmse={us['cte_rmse_m']:.3f} m")
        results["understeer"][plat] = us

    out_path = ROOT / "out" / "baseline_scores.json"
    out_path.write_text(json.dumps(results, indent=2))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
