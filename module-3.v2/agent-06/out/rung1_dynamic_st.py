"""Rung-1 minimum-viable attempt: linear dynamic single-track with slip angles.

State per step: yaw rate r, lateral velocity v_y.
Inputs: u (longitudinal speed = v_mps), delta (road wheel angle).
Bicycle linear-tyre model:
    alpha_f = (v_y + l_f * r) / u - delta
    alpha_r = (v_y - l_r * r) / u
    F_yf = -C_f * alpha_f
    F_yr = -C_r * alpha_r
    m * dv_y_dt = F_yf + F_yr - m * u * r
    I_z * dr_dt = l_f * F_yf - l_r * F_yr

Discretised explicit Euler over the segment's own dt.
Compared against rung-0 shipped model on a held-out subset.
"""
import sys, json, math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v2/agent-06")
sys.path.insert(0, str(ROOT / "skills" / "score-model"))
sys.path.insert(0, str(ROOT / "out"))

from score import score
from predict_v1 import predict as rung0_predict

# Openpilot-canonical params from code/parameters.py
PARAMS = {
    "FORD_F_150_LIGHTNING_MK1": dict(m=3084.0, I_z=9903.37, l_f=1.628, l_r=2.072,
                                      C_f=378307.0, C_r=469878.0, delta0=0.00133),
    "FORD_MUSTANG_MACH_E_MK1":  dict(m=2336.0, I_z=4879.05, l_f=1.313, l_r=1.671,
                                      C_f=286551.0, C_r=355912.0, delta0=-0.0001),
    "HYUNDAI_IONIQ_5":          dict(m=2100.0, I_z=4500.0,  l_f=1.40,  l_r=1.60,
                                      C_f=300000.0, C_r=370000.0, delta0=0.0),
}


def _per_segment_delta0(sim_df, fallback=0.0):
    v = sim_df["v_mps"].to_numpy()
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
    mask = (np.abs(yr_v0) < 0.03) & (v > 5.0)
    if int(mask.sum()) < 50:
        return fallback
    return float(sim_df.loc[mask, "delta_road_rad"].median())


def rung1_predict(sim_df, platform):
    if platform not in PARAMS:
        return pd.DataFrame({"yaw_rate_pred_rads": sim_df["yaw_rate_pred_rads"].to_numpy()},
                            index=sim_df.index)
    p = PARAMS[platform]
    # Per-segment delta0 for Mach-E + IONIQ-5
    if platform in ("FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"):
        delta0 = _per_segment_delta0(sim_df, fallback=p["delta0"])
    else:
        delta0 = p["delta0"]

    t = sim_df["t_s"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    delta_road = sim_df["delta_road_rad"].to_numpy() - delta0

    dt = np.diff(t, prepend=t[0])
    N = len(t)
    r = np.zeros(N)  # yaw rate
    vy = np.zeros(N)
    m = p["m"]; I_z = p["I_z"]
    l_f = p["l_f"]; l_r = p["l_r"]
    C_f = p["C_f"]; C_r = p["C_r"]
    eps = 0.3

    # Backward Euler (semi-implicit): stable for stiff tyre forces.
    # Discrete linear system x_{k+1} = (I - h A)^-1 (x_k + h B delta)
    # x = [vy, r],
    # A = [[ -(C_f+C_r)/(m u),  -u - (l_f C_f - l_r C_r)/(m u) ],
    #      [ -(l_f C_f - l_r C_r)/(I_z u), -(l_f^2 C_f + l_r^2 C_r)/(I_z u)]]
    # B = [ C_f/m, l_f C_f / I_z ]
    for i in range(1, N):
        u = max(v[i-1], eps)
        d = delta_road[i-1]
        h = dt[i]
        a11 = -(C_f + C_r) / (m * u)
        a12 = -u - (l_f * C_f - l_r * C_r) / (m * u)
        a21 = -(l_f * C_f - l_r * C_r) / (I_z * u)
        a22 = -(l_f*l_f*C_f + l_r*l_r*C_r) / (I_z * u)
        b1 = C_f / m
        b2 = l_f * C_f / I_z
        # (I - h A) X_new = X_old + h B * d
        M11 = 1 - h*a11; M12 = -h*a12
        M21 = -h*a21;    M22 = 1 - h*a22
        det = M11*M22 - M12*M21
        if det == 0 or not np.isfinite(det):
            vy[i] = vy[i-1]; r[i] = r[i-1]
            continue
        rhs1 = vy[i-1] + h * b1 * d
        rhs2 = r[i-1]  + h * b2 * d
        vy[i] = (M22 * rhs1 - M12 * rhs2) / det
        r[i]  = (-M21 * rhs1 + M11 * rhs2) / det

    return pd.DataFrame({"yaw_rate_pred_rads": r}, index=sim_df.index)


if __name__ == "__main__":
    # Score on the full dataset.
    paths = sorted((ROOT / "data" / "sim" / "segments").glob("*/**/sim.csv"))
    print(f"# segments: {len(paths)}")

    # Reset coeffs.json to shipped values for rung-0 baseline comparison
    import shutil
    shutil.copy(ROOT / "final-model" / "coeffs.json", ROOT / "out" / "coeffs.json")

    print("\n--- Rung 0 (shipped) ---")
    res0 = score(rung0_predict, segment_paths=paths)
    print(f"yaw={res0['yaw_rate_rmse']:.6f} cte={res0['cte_rmse']:.4f}")

    print("\n--- Rung 1 (linear dynamic ST, explicit Euler) ---")
    res1 = score(rung1_predict, segment_paths=paths)
    print(f"yaw={res1['yaw_rate_rmse']:.6f} cte={res1['cte_rmse']:.4f}")
    for plat, m in res1["per_platform"].items():
        print(f"  {plat}: yaw={m['yaw_rate_rmse']:.5f} cte={m['cte_rmse']:.3f}")
