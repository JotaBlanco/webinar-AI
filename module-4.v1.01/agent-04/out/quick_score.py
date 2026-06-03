"""Fast pooled scorer for candidate predict functions.

Reads sim/segments/, hands stripped allowlist sim_df to predict(),
computes pooled yaw-rate RMSE (v>2) and pooled distance-resampled CTE RMSE.
"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-04")
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import integrate_trajectory  # noqa: E402

ALLOWED = {
    "t_s", "delta_wheel_deg", "delta_road_rad", "v_mps", "a_long_mps2",
    "accel_pedal_pct", "brake_pressed", "brake_pedal_state", "steer_rate_dps",
    "yaw_rate_pred_rads", "di_torque_actual_nm",
    "wheel_FL_kph", "wheel_FR_kph", "wheel_RL_kph", "wheel_RR_kph",
}

PLATFORM_SCHEMA = {
    "FORD_F_150_LIGHTNING_MK1": {"truth": "yaw_rate_meas_rads", "baseline": "yaw_rate_pred_rads"},
    "FORD_MUSTANG_MACH_E_MK1":  {"truth": "yaw_rate_meas_rads", "baseline": "yaw_rate_pred_rads"},
    "HYUNDAI_IONIQ_5":          {"truth": "yaw_rate_meas_rads", "baseline": "yaw_rate_pred_rads"},
    "TESLA_MODEL_3":            {"truth": "psi_dot_rads",       "baseline": "psi_dot_rads"},
}


def find_segments(root: Path = None, platforms: list[str] | None = None) -> list[Path]:
    root = root or (ROOT / "data" / "sim" / "segments")
    paths = sorted(p for p in root.glob("*/**/sim.csv") if p.is_file())
    if platforms:
        paths = [p for p in paths if any(pl in str(p) for pl in platforms)]
    return paths


def platform_from(p: Path) -> str:
    return p.resolve().parents[3].name


def cte_rmse_segment(t: np.ndarray, v: np.ndarray, yr_pred: np.ndarray,
                     yr_true: np.ndarray, grid: float = 1.0, min_d: float = 20.0):
    if len(t) < 2:
        return None, 0
    dt = np.diff(t)
    n = len(t)
    s_p, x_p, y_p, _ = integrate_trajectory(dt, v, yr_pred)
    s_t, x_t, y_t, _ = integrate_trajectory(dt, v, yr_true)
    s_max = min(s_p[-1], s_t[-1])
    if s_max < min_d:
        return None, 0
    grid_s = np.arange(grid, s_max, grid)
    xp = np.interp(grid_s, s_p, x_p)
    yp = np.interp(grid_s, s_p, y_p)
    xt = np.interp(grid_s, s_t, x_t)
    yt = np.interp(grid_s, s_t, y_t)
    d2 = (xp - xt) ** 2 + (yp - yt) ** 2
    return float(np.sqrt(d2.mean())), len(grid_s)


def score(predict_fn, segments: list[Path] | None = None, v_floor: float = 2.0):
    segments = segments or find_segments()
    yaw_sq_sum = 0.0
    yaw_n = 0
    cte_sq_sum = 0.0
    cte_n = 0
    per_platform = {}
    for p in segments:
        plat = platform_from(p)
        sch = PLATFORM_SCHEMA.get(plat)
        if not sch:
            continue
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if sch["truth"] not in df.columns:
            continue
        sim_in = df[[c for c in df.columns if c in ALLOWED]].copy()
        if "yaw_rate_pred_rads" not in sim_in.columns and sch["baseline"] in df.columns:
            sim_in["yaw_rate_pred_rads"] = df[sch["baseline"]].astype(float).to_numpy()
        try:
            out = predict_fn(sim_in, plat)
        except Exception as e:
            continue
        if "yaw_rate_pred_rads" not in out.columns:
            continue
        yr_pred = out["yaw_rate_pred_rads"].to_numpy()
        yr_true = df[sch["truth"]].to_numpy()
        v = df["v_mps"].to_numpy()
        t = df["t_s"].to_numpy()
        mask = v > v_floor
        if mask.any():
            res = yr_pred[mask] - yr_true[mask]
            yaw_sq_sum += float((res ** 2).sum())
            yaw_n += int(mask.sum())
            pp = per_platform.setdefault(plat, {"yaw_sq": 0.0, "yaw_n": 0, "cte_sq": 0.0, "cte_n": 0, "res_sum": 0.0})
            pp["yaw_sq"] += float((res ** 2).sum())
            pp["yaw_n"] += int(mask.sum())
            pp["res_sum"] += float(res.sum())
        cte_rmse, n_bins = cte_rmse_segment(t, v, yr_pred, yr_true)
        if cte_rmse is not None:
            cte_sq_sum += (cte_rmse ** 2) * n_bins
            cte_n += n_bins
            pp = per_platform.setdefault(plat, {"yaw_sq": 0.0, "yaw_n": 0, "cte_sq": 0.0, "cte_n": 0, "res_sum": 0.0})
            pp["cte_sq"] += (cte_rmse ** 2) * n_bins
            pp["cte_n"] += n_bins
    yaw_rmse = float(np.sqrt(yaw_sq_sum / yaw_n)) if yaw_n else float("nan")
    cte_rmse = float(np.sqrt(cte_sq_sum / cte_n)) if cte_n else float("nan")
    pp_out = {}
    for k, v in per_platform.items():
        pp_out[k] = {
            "yaw_rmse": float(np.sqrt(v["yaw_sq"] / v["yaw_n"])) if v["yaw_n"] else None,
            "yaw_bias": v["res_sum"] / v["yaw_n"] if v["yaw_n"] else None,
            "cte_rmse": float(np.sqrt(v["cte_sq"] / v["cte_n"])) if v["cte_n"] else None,
            "n_yaw": v["yaw_n"],
            "n_cte": v["cte_n"],
        }
    return {"yaw_rate_rmse": yaw_rmse, "cte_rmse": cte_rmse, "per_platform": pp_out, "n_segments": len(segments)}


if __name__ == "__main__":
    import importlib.util
    spec = importlib.util.spec_from_file_location("v1", str(ROOT / "code" / "v1_baseline.py"))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    r = score(m.predict_v1)
    print("V1 baseline pooled:")
    print(f"  yaw_rate_rmse = {r['yaw_rate_rmse']:.6f} rad/s")
    print(f"  cte_rmse      = {r['cte_rmse']:.4f} m")
    for plat, pp in r["per_platform"].items():
        print(f"  {plat}: yaw={pp['yaw_rmse']:.6f} bias={pp['yaw_bias']:+.6f} cte={pp['cte_rmse']:.3f}")
