"""Fit per-platform coefficients against the joint yaw + CTE objective.

Uses scipy.optimize.minimize (Nelder-Mead) with multiple restarts.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "_shared"))
sys.path.insert(0, str(ROOT / "final-model"))

from predict import _predict_platform, _per_segment_delta0  # noqa: E402
from traj_metrics import cte_diagnostics_segment  # noqa: E402


def gather_segments(platform: str, max_segments: int | None = None,
                    stride: int | None = None) -> list[pd.DataFrame]:
    """Load training segments for a platform (has truth column).

    If max_segments is set, takes an evenly-strided sample to keep optimisation fast.
    """
    root = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(root.glob("*/**/sim.csv"))
    if max_segments is not None and len(paths) > max_segments:
        step = max(1, len(paths) // max_segments)
        paths = paths[::step][:max_segments]
    elif stride is not None and stride > 1:
        paths = paths[::stride]
    dfs = []
    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns or "v_mps" not in df.columns:
            continue
        dfs.append(df)
    return dfs


def score_segments(segments: list[pd.DataFrame], params: dict,
                   sample_filter_v_mps: float = 2.0, lam_cte: float = 0.5) -> tuple[float, float, float]:
    """Return (yaw_rmse, cte_rmse, combined_loss) pooled across segments."""
    yaw_sum_sq = 0.0
    yaw_n = 0
    cte_sum_sq = 0.0
    cte_n = 0
    for df in segments:
        t = df["t_s"].to_numpy(dtype=float)
        v = df["v_mps"].to_numpy(dtype=float)
        truth = df["yaw_rate_meas_rads"].to_numpy(dtype=float)

        yr_pred = _predict_platform(df, params)

        m = v > sample_filter_v_mps
        r = yr_pred[m] - truth[m]
        yaw_sum_sq += float(np.sum(r * r))
        yaw_n += int(m.sum())

        if len(t) >= 2 and np.all(np.diff(t) > 0):
            cte = cte_diagnostics_segment(t, v, truth, yr_pred, grid_step_m=1.0, min_distance_m=20.0)
            cte_sum_sq += cte["sum_sq_m2"]
            cte_n += cte["n_bins"]

    yaw_rmse = math.sqrt(yaw_sum_sq / yaw_n) if yaw_n > 0 else float("nan")
    cte_rmse = math.sqrt(cte_sum_sq / cte_n) if cte_n > 0 else float("nan")
    # Normalised composite loss
    loss = yaw_rmse / 0.01 + lam_cte * cte_rmse / 50.0
    return yaw_rmse, cte_rmse, loss


def fit_platform(platform: str, use_per_segment_delta0: bool,
                 init: dict, bounds: dict, lam_cte: float = 0.5,
                 max_segments: int | None = 150) -> dict:
    print(f"\n=== Fitting {platform}  use_per_segment_delta0={use_per_segment_delta0} ===")
    segments = gather_segments(platform, max_segments=max_segments)
    print(f"  loaded {len(segments)} segments (max {max_segments})")
    if not segments:
        return init

    if use_per_segment_delta0:
        keys = ["g", "L_eff", "K_us", "tau", "delta0_fallback"]
    else:
        keys = ["g", "L_eff", "K_us", "tau", "delta0"]

    x0 = np.array([init[k] for k in keys])
    lo = np.array([bounds[k][0] for k in keys])
    hi = np.array([bounds[k][1] for k in keys])

    def unpack(x):
        p = dict(init)
        for k, val in zip(keys, x):
            p[k] = float(val)
        p["use_per_segment_delta0"] = use_per_segment_delta0
        return p

    def objective(x):
        # soft bound penalty
        if np.any(x < lo) or np.any(x > hi):
            return 1e6 + float(np.sum(np.maximum(lo - x, 0)) + np.sum(np.maximum(x - hi, 0))) * 1e4
        p = unpack(x)
        yaw, cte, loss = score_segments(segments, p, lam_cte=lam_cte)
        if not np.isfinite(loss):
            return 1e6
        return loss

    res = minimize(objective, x0, method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-5, "maxiter": 400, "disp": False})
    best_p = unpack(res.x)
    yaw, cte, loss = score_segments(segments, best_p, lam_cte=lam_cte)
    print(f"  fitted: yaw={yaw:.5f}, cte={cte:.3f}, loss={loss:.3f}")
    print(f"  params: {best_p}")
    return best_p


def main():
    # Initial guesses informed by anti-patterns.md priors and platform priors.
    fits = {}

    # Mach-E — per-segment δ₀ ON (wide segment bias spread).
    fits["FORD_MUSTANG_MACH_E_MK1"] = fit_platform(
        "FORD_MUSTANG_MACH_E_MK1",
        use_per_segment_delta0=True,
        init={"g": 0.89, "L_eff": 2.85, "K_us": 0.0020, "tau": 0.07, "delta0_fallback": 0.0,
              "v_thresh": 8.0, "delta_thresh": 0.005, "min_rows": 80},
        bounds={"g": (0.5, 1.5), "L_eff": (2.0, 4.0), "K_us": (0.0, 0.02),
                "tau": (0.0, 0.30), "delta0_fallback": (-0.02, 0.02)},
    )

    # Lightning — global δ₀ (tight spread).
    fits["FORD_F_150_LIGHTNING_MK1"] = fit_platform(
        "FORD_F_150_LIGHTNING_MK1",
        use_per_segment_delta0=False,
        init={"g": 0.86, "L_eff": 3.5, "K_us": 0.0035, "tau": 0.06, "delta0": 0.001},
        bounds={"g": (0.5, 1.5), "L_eff": (2.5, 4.5), "K_us": (0.0, 0.02),
                "tau": (0.0, 0.30), "delta0": (-0.02, 0.02)},
    )

    # Hyundai — try per-segment δ₀ on first; we'll evaluate at the end.
    fits["HYUNDAI_IONIQ_5"] = fit_platform(
        "HYUNDAI_IONIQ_5",
        use_per_segment_delta0=True,
        init={"g": 0.95, "L_eff": 2.9, "K_us": 0.003, "tau": 0.07, "delta0_fallback": 0.0,
              "v_thresh": 8.0, "delta_thresh": 0.005, "min_rows": 80},
        bounds={"g": (0.5, 1.5), "L_eff": (2.0, 4.0), "K_us": (0.0, 0.02),
                "tau": (0.0, 0.30), "delta0_fallback": (-0.02, 0.02)},
    )

    out = Path(__file__).resolve().parent / "coeffs.json"
    final_path = ROOT / "final-model" / "coeffs.json"
    with open(out, "w") as f:
        json.dump(fits, f, indent=2)
    with open(final_path, "w") as f:
        json.dump(fits, f, indent=2)
    print(f"\nWrote {out} and {final_path}")


if __name__ == "__main__":
    main()
