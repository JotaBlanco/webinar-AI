"""Per-platform coefficient fit for the rung-0 KS + understeer + lag model
with an input-derived per-segment δ₀.

Operating-contract reminder: at grading time the inputs are restricted to
ALLOWED_INPUT_COLUMNS (no a_lat_meas_mps2, no truth). We detect "straight"
rows from delta_road_rad alone, NOT from a_lat_meas.
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3/agent-06")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "_shared"))

from score import score  # noqa: E402
from traj_metrics import cte_diagnostics_segment  # noqa: E402

PLATFORM_TRUTH = {
    "FORD_F_150_LIGHTNING_MK1": "yaw_rate_meas_rads",
    "FORD_MUSTANG_MACH_E_MK1":  "yaw_rate_meas_rads",
    "HYUNDAI_IONIQ_5":          "yaw_rate_meas_rads",
}


# ---- model -----------------------------------------------------------------

def _per_segment_delta0_from_inputs(delta_road: np.ndarray, v: np.ndarray,
                                    delta_thresh: float = 0.005,
                                    v_thresh: float = 5.0,
                                    min_rows: int = 50,
                                    fallback: float = 0.0) -> float:
    """Detect straight-driving from inputs alone (no a_lat_meas).

    A row is "straight" if |delta_road_rad| < delta_thresh AND v > v_thresh.
    On such rows any nonzero δ is offset, not steering input.
    """
    mask = (np.abs(delta_road) < delta_thresh) & (v > v_thresh)
    if int(mask.sum()) < min_rows:
        return fallback
    return float(np.median(delta_road[mask]))


def _predict_one(sim_df: pd.DataFrame, p: dict) -> np.ndarray:
    """Rung-0 KS + understeer + first-order lag.

    Params:
      g     : steering scale
      delta0: global steering offset
      use_per_segment_delta0 : if True, override delta0 with per-segment estimate
      K_us  : understeer coefficient (rad/(m/s)^2 essentially)
      L_eff : effective wheelbase (m)
      tau   : first-order lag time constant (s)
    """
    delta_road = sim_df["delta_road_rad"].to_numpy(dtype=float)
    v = sim_df["v_mps"].to_numpy(dtype=float)
    t = sim_df["t_s"].to_numpy(dtype=float)

    if p.get("use_per_segment_delta0", False):
        delta0 = _per_segment_delta0_from_inputs(
            delta_road, v,
            delta_thresh=p.get("delta0_detect_thresh", 0.005),
            v_thresh=5.0,
            min_rows=50,
            fallback=p.get("delta0_fallback", p.get("delta0", 0.0)),
        )
    else:
        delta0 = p["delta0"]

    delta = (delta_road - delta0) * p["g"]
    yr_ss = v * delta / (p["L_eff"] + p["K_us"] * v * v)

    tau = max(p["tau"], 1e-4)
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (tau + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i - 1] - yr[i - 1])
        # Use yr_ss at i-1 -- standard zero-order hold update -- but the
        # canonical lag uses yr_ss[i]; both very close. Try yr_ss[i]:
    # second-pass with yr_ss[i] to match anti-patterns sample
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i - 1] + alpha[i] * (yr_ss[i] - yr[i - 1])
    return yr


# ---- pooled-segment loss ---------------------------------------------------

def load_platform_segments(platform: str) -> list[dict]:
    """Pre-load segments for a platform with the needed columns into memory."""
    truth = PLATFORM_TRUTH[platform]
    base = ROOT / "data" / "sim" / "segments" / platform
    paths = sorted(p for p in base.glob("*/**/sim.csv") if p.is_file())
    segs = []
    for p in paths:
        try:
            df = pd.read_csv(p, usecols=lambda c: c in {
                "t_s", "delta_road_rad", "v_mps", truth,
            })
        except Exception:
            continue
        if not {"t_s", "delta_road_rad", "v_mps", truth} <= set(df.columns):
            continue
        t = df["t_s"].to_numpy(dtype=float)
        if len(t) < 50 or np.any(np.diff(t) <= 0):
            continue
        segs.append({
            "path":  str(p),
            "t":     t,
            "v":     df["v_mps"].to_numpy(dtype=float),
            "delta": df["delta_road_rad"].to_numpy(dtype=float),
            "truth": df[truth].to_numpy(dtype=float),
        })
    return segs


def loss_for_platform(coeffs: dict, segs: list[dict],
                      w_yaw: float = 1.0, w_cte: float = 1.0,
                      grid_step_m: float = 1.0, min_distance_m: float = 20.0,
                      v_thresh: float = 2.0) -> dict:
    yaw_sum_sq = 0.0
    yaw_n = 0
    cte_sum_sq = 0.0
    cte_n = 0
    for seg in segs:
        # Build a thin sim_df-like dict
        dummy = pd.DataFrame({
            "t_s": seg["t"], "delta_road_rad": seg["delta"], "v_mps": seg["v"],
        })
        yr_pred = _predict_one(dummy, coeffs)
        # yaw RMSE (v-filtered)
        mask = seg["v"] > v_thresh
        if mask.any():
            r = (yr_pred - seg["truth"])[mask]
            yaw_sum_sq += float(np.sum(r * r))
            yaw_n += int(mask.sum())
        # CTE
        cte = cte_diagnostics_segment(
            seg["t"], seg["v"], seg["truth"], yr_pred,
            grid_step_m=grid_step_m, min_distance_m=min_distance_m,
        )
        cte_sum_sq += cte["sum_sq_m2"]
        cte_n += cte["n_bins"]
    yaw_rmse = math.sqrt(yaw_sum_sq / yaw_n) if yaw_n > 0 else float("nan")
    cte_rmse = math.sqrt(cte_sum_sq / cte_n) if cte_n > 0 else float("nan")
    return {"yaw_rmse": yaw_rmse, "cte_rmse": cte_rmse,
            "yaw_sum_sq": yaw_sum_sq, "yaw_n": yaw_n,
            "cte_sum_sq": cte_sum_sq, "cte_n": cte_n,
            "loss": w_yaw * yaw_rmse + w_cte * cte_rmse * 0.001}  # scale CTE


def fit_platform(platform: str,
                 use_per_segment_delta0: bool,
                 initial: dict,
                 bounds: dict,
                 w_yaw: float = 1.0,
                 w_cte: float = 1.0) -> dict:
    segs = load_platform_segments(platform)
    print(f"[{platform}] loaded {len(segs)} segments")
    if not segs:
        return initial

    keys = ["g", "delta0", "K_us", "L_eff", "tau"]
    x0 = np.array([initial[k] for k in keys], dtype=float)
    lo = np.array([bounds[k][0] for k in keys], dtype=float)
    hi = np.array([bounds[k][1] for k in keys], dtype=float)

    def to_coeffs(x):
        c = {k: float(x[i]) for i, k in enumerate(keys)}
        c["use_per_segment_delta0"] = use_per_segment_delta0
        if use_per_segment_delta0:
            c["delta0_fallback"] = c["delta0"]
        return c

    def obj(x):
        c = to_coeffs(x)
        r = loss_for_platform(c, segs, w_yaw=w_yaw, w_cte=w_cte)
        return r["loss"]

    # Use Nelder-Mead (no gradient) — robust for tiny param vector
    res = minimize(obj, x0, method="Nelder-Mead",
                   options={"xatol": 1e-5, "fatol": 1e-5, "maxiter": 400, "disp": False})
    # Clip to bounds (Nelder-Mead doesn't enforce)
    x = np.clip(res.x, lo, hi)
    fitted = to_coeffs(x)
    metrics = loss_for_platform(fitted, segs, w_yaw=w_yaw, w_cte=w_cte)
    print(f"[{platform}] fit done. yaw_rmse={metrics['yaw_rmse']:.5f} "
          f"cte_rmse={metrics['cte_rmse']:.3f}  coeffs={fitted}")
    return fitted


# Default starting points (drawn from anti-patterns.md sample where applicable)
DEFAULTS = {
    "FORD_F_150_LIGHTNING_MK1": {
        "use_per_segment_delta0": False,
        "initial": {"g": 0.863, "delta0": 0.00133, "K_us": 0.00350, "L_eff": 3.26, "tau": 0.060},
        "bounds":  {"g": (0.4, 1.4), "delta0": (-0.02, 0.02), "K_us": (0.0, 0.02),
                    "L_eff": (2.5, 4.5), "tau": (0.0, 0.5)},
    },
    "FORD_MUSTANG_MACH_E_MK1": {
        "use_per_segment_delta0": True,
        "initial": {"g": 0.891, "delta0": -0.0001, "K_us": 0.00202, "L_eff": 2.22, "tau": 0.069},
        "bounds":  {"g": (0.4, 1.4), "delta0": (-0.02, 0.02), "K_us": (0.0, 0.02),
                    "L_eff": (1.8, 3.5), "tau": (0.0, 0.5)},
    },
    "HYUNDAI_IONIQ_5": {
        "use_per_segment_delta0": True,
        "initial": {"g": 0.9, "delta0": 0.0, "K_us": 0.003, "L_eff": 3.0, "tau": 0.060},
        "bounds":  {"g": (0.4, 1.4), "delta0": (-0.02, 0.02), "K_us": (0.0, 0.02),
                    "L_eff": (2.3, 3.8), "tau": (0.0, 0.5)},
    },
}


def main():
    out = {}
    for plat, cfg in DEFAULTS.items():
        fitted = fit_platform(
            plat,
            use_per_segment_delta0=cfg["use_per_segment_delta0"],
            initial=cfg["initial"],
            bounds=cfg["bounds"],
            w_yaw=1.0, w_cte=1.0,
        )
        out[plat] = fitted
    # Tesla: no truth; pass-through
    out["TESLA_MODEL_3"] = {"passthrough": True}

    coeffs_path = ROOT / "final-model" / "coeffs.json"
    coeffs_path.write_text(json.dumps(out, indent=2))
    print(f"\nwrote {coeffs_path}")


if __name__ == "__main__":
    main()
