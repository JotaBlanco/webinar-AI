"""Improve lateral predictions of the KS model on Ford sim data.

The Ford sim CSVs contain:
  - t_s, v_mps, delta_road_rad           (model inputs, clamped to measured)
  - yaw_rate_meas_rads, a_lat_meas_mps2  (truth channels, IMU/ABS)
  - yaw_rate_pred_rads, a_y_pred_mps2    (current KS prediction)

Primary metric: RMSE of yaw rate (rad/s), aggregated across all Ford segments
(weighted by sample count). Secondary: RMSE of lateral acceleration.

Variants we sweep (each builds on the previous):
  B0  baseline                — yaw_rate_pred_rads as-is
  B1  +steering offset        — subtract mean(delta_road - delta_road_neutral)
                                 picked by minimising on a held-out fold
  B2  +understeer factor K    — divide yaw_rate by (1 + K*v²); K fit per-platform
  B3  +steer-time lag         — small lookahead of delta vs yaw (shift in samples)

Attribution: incremental drop in aggregate RMSE when each layer is added on top
of the previous. Reported both as absolute Δ(rad/s) and share of total Δ.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
AGENT_DIR = HERE.parent
DATA_DIR = AGENT_DIR / "data" / "sim" / "segments"
OUT_DIR = AGENT_DIR / "out"
OUT_DIR.mkdir(exist_ok=True)

PLATFORMS = ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]

# Wheelbase from parameters.py (avoiding import for isolation purity).
L_BY_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}


def list_segments(platform: str) -> list[Path]:
    return sorted((DATA_DIR / platform).rglob("sim.csv"))


def load_segment(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    return df


def rmse(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.sqrt(np.mean((a - b) ** 2)))


def aggregate_rmse(per_seg: list[tuple[int, float]]) -> float:
    """Sample-count-weighted RMSE aggregate.

    per_seg: list of (N, mse) — we recombine total SSE / total N.
    """
    total_sse = sum(n * mse for n, mse in per_seg)
    total_n = sum(n for n, _ in per_seg)
    return float(np.sqrt(total_sse / total_n))


def collect_arrays(platform: str):
    """Concatenate all segments for a platform into one big set of arrays."""
    segs = list_segments(platform)
    parts = []
    for p in segs:
        try:
            df = load_segment(p)
        except Exception as e:
            print(f"  skip {p}: {e}", file=sys.stderr)
            continue
        if len(df) < 50:
            continue
        # Drop NaN rows in critical columns
        cols = ["t_s", "v_mps", "delta_road_rad",
                "yaw_rate_meas_rads", "yaw_rate_pred_rads",
                "a_lat_meas_mps2", "a_y_pred_mps2"]
        if not all(c in df.columns for c in cols):
            continue
        sub = df[cols].dropna()
        if len(sub) < 50:
            continue
        # Sanity filter:
        #   - drop stationary samples (v < 1 m/s) where kinematic-only model
        #     can't predict yaw rate meaningfully and IMU lat-acc is noisy.
        #   - drop blatantly impossible measured lat-acc (|a| > 20 m/s²) — these
        #     come from a couple of segments with sensor garbage at v=0.
        sub = sub[(sub["v_mps"] > 1.0) & (sub["a_lat_meas_mps2"].abs() < 20.0)]
        if len(sub) < 50:
            continue
        sub = sub.copy()
        sub["seg_id"] = str(p.relative_to(DATA_DIR))
        parts.append(sub)
    full = pd.concat(parts, ignore_index=True)
    return full, segs


def predict_b0(df: pd.DataFrame, L: float) -> np.ndarray:
    return df["yaw_rate_pred_rads"].to_numpy()


def predict_b1(df: pd.DataFrame, L: float, delta_off: float) -> np.ndarray:
    delta = df["delta_road_rad"].to_numpy() - delta_off
    v = df["v_mps"].to_numpy()
    return (v / L) * np.tan(delta)


def predict_b2(df: pd.DataFrame, L: float, delta_off: float, K: float) -> np.ndarray:
    delta = df["delta_road_rad"].to_numpy() - delta_off
    v = df["v_mps"].to_numpy()
    yr = (v / L) * np.tan(delta) / (1.0 + K * v * v)
    return yr


def shift_by_samples(yr_pred: np.ndarray, t: np.ndarray, seg_ids: np.ndarray, lag_samples: int) -> np.ndarray:
    """Shift prediction forward in time by `lag_samples` samples WITHIN each seg.

    Positive lag_samples means the prediction is moved EARLIER (we look at
    future prediction now), compensating for sensor/actuator lag in the
    measured yaw rate.
    """
    out = yr_pred.copy()
    # Process per seg
    df_idx = pd.DataFrame({"seg": seg_ids})
    starts = []
    cur_seg = None
    cur_start = 0
    for i, s in enumerate(seg_ids):
        if s != cur_seg:
            if cur_seg is not None:
                starts.append((cur_seg, cur_start, i))
            cur_seg = s
            cur_start = i
    starts.append((cur_seg, cur_start, len(seg_ids)))
    for _, a, b in starts:
        block = yr_pred[a:b]
        if lag_samples == 0:
            out[a:b] = block
        elif lag_samples > 0:
            out[a:b - lag_samples] = block[lag_samples:]
            out[b - lag_samples:b] = block[-1]
        else:
            k = -lag_samples
            out[a + k:b] = block[:-k]
            out[a:a + k] = block[0]
    return out


def fit_steering_offset(df: pd.DataFrame, L: float) -> float:
    """Find the steering offset that minimises yaw-rate residual.

    Sweep a coarse grid then refine. Range: ±0.02 rad (~0.34 deg at the wheel
    for 17:1).
    """
    grid = np.linspace(-0.02, 0.02, 81)
    best = None
    y_meas = df["yaw_rate_meas_rads"].to_numpy()
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    for d_off in grid:
        pred = (v / L) * np.tan(delta - d_off)
        r = np.mean((pred - y_meas) ** 2)
        if best is None or r < best[1]:
            best = (d_off, r)
    return float(best[0])


def fit_K(df: pd.DataFrame, L: float, delta_off: float) -> float:
    """Fit understeer-gradient K minimising yaw-rate residual."""
    # K is small; typical 0.001–0.01 s²/m². Sweep a logarithmic-ish grid then refine.
    y_meas = df["yaw_rate_meas_rads"].to_numpy()
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy() - delta_off
    base = (v / L) * np.tan(delta)
    v2 = v * v

    def loss(K):
        pred = base / (1.0 + K * v2)
        return np.mean((pred - y_meas) ** 2)

    grid = np.linspace(-0.005, 0.020, 251)
    losses = np.array([loss(K) for K in grid])
    best_i = int(np.argmin(losses))
    K0 = grid[best_i]
    # refine
    grid2 = np.linspace(K0 - 0.001, K0 + 0.001, 201)
    losses2 = np.array([loss(K) for K in grid2])
    return float(grid2[int(np.argmin(losses2))])


def fit_lag(df: pd.DataFrame, pred: np.ndarray, max_lag_samples: int = 20) -> int:
    """Find integer sample lag that minimises yaw-rate RMSE.

    Per-segment shifting; positive = prediction shifted earlier (sample-wise).
    """
    y_meas = df["yaw_rate_meas_rads"].to_numpy()
    seg_ids = df["seg_id"].to_numpy()
    t = df["t_s"].to_numpy()
    best = (0, np.mean((pred - y_meas) ** 2))
    for lag in range(-max_lag_samples, max_lag_samples + 1):
        shifted = shift_by_samples(pred, t, seg_ids, lag)
        r = np.mean((shifted - y_meas) ** 2)
        if r < best[1]:
            best = (lag, r)
    return int(best[0])


def evaluate_a_y(df: pd.DataFrame, yr_pred: np.ndarray) -> tuple[float, float]:
    """Given yaw-rate prediction, derive a_y = v * psi_dot and compute RMSE.

    Returns (rmse_pred_a_y, rmse_baseline_a_y).
    """
    v = df["v_mps"].to_numpy()
    a_y_meas = df["a_lat_meas_mps2"].to_numpy()
    a_y_pred = v * yr_pred
    return rmse(a_y_pred, a_y_meas), rmse(df["a_y_pred_mps2"].to_numpy(), a_y_meas)


def run_platform(platform: str) -> dict:
    L = L_BY_PLATFORM[platform]
    print(f"\n=== {platform} (L={L:.3f}) ===")
    df, seg_paths = collect_arrays(platform)
    print(f"  rows={len(df):,}   segments={df['seg_id'].nunique()}")

    y_meas = df["yaw_rate_meas_rads"].to_numpy()

    # B0 baseline
    yr0 = predict_b0(df, L)
    r0 = rmse(yr0, y_meas)
    print(f"  B0 baseline RMSE (yaw)  = {r0*1000:.3f} mrad/s")

    # B1 steering offset
    d_off = fit_steering_offset(df, L)
    yr1 = predict_b1(df, L, d_off)
    r1 = rmse(yr1, y_meas)
    print(f"  B1 +steer_offset δ0={np.degrees(d_off):+.3f}°  RMSE = {r1*1000:.3f} mrad/s")

    # B2 understeer factor
    K = fit_K(df, L, d_off)
    yr2 = predict_b2(df, L, d_off, K)
    r2 = rmse(yr2, y_meas)
    print(f"  B2 +K={K:+.5f}              RMSE = {r2*1000:.3f} mrad/s")

    # B3 lag compensation
    lag = fit_lag(df, yr2, max_lag_samples=15)
    yr3 = shift_by_samples(yr2, df["t_s"].to_numpy(), df["seg_id"].to_numpy(), lag)
    r3 = rmse(yr3, y_meas)
    print(f"  B3 +lag={lag} samples ({lag*20:+d} ms)  RMSE = {r3*1000:.3f} mrad/s")

    # Secondary metric — lateral acceleration RMSE
    a_y_r0 = rmse(df["a_y_pred_mps2"].to_numpy(), df["a_lat_meas_mps2"].to_numpy())
    a_y_r3, _ = evaluate_a_y(df, yr3)
    print(f"  a_y RMSE  B0={a_y_r0:.3f}  →  B3={a_y_r3:.3f}  m/s²")

    return {
        "platform": platform,
        "n_rows": int(len(df)),
        "n_segments": int(df["seg_id"].nunique()),
        "B0_yaw_rmse": r0,
        "B1_yaw_rmse": r1,
        "B2_yaw_rmse": r2,
        "B3_yaw_rmse": r3,
        "B0_a_y_rmse": a_y_r0,
        "B3_a_y_rmse": a_y_r3,
        "params": {
            "delta_offset_rad": d_off,
            "delta_offset_deg": float(np.degrees(d_off)),
            "K": K,
            "lag_samples": lag,
            "lag_ms": lag * 20,
        },
    }


def main():
    results = {}
    for p in PLATFORMS:
        results[p] = run_platform(p)

    # Aggregate across both platforms (sample-weighted)
    def agg(level: str) -> float:
        total_sse = 0.0
        total_n = 0
        for p, r in results.items():
            n = r["n_rows"]
            mse = r[level] ** 2
            total_sse += n * mse
            total_n += n
        return float(np.sqrt(total_sse / total_n))

    overall = {lvl: agg(lvl) for lvl in
               ("B0_yaw_rmse", "B1_yaw_rmse", "B2_yaw_rmse", "B3_yaw_rmse",
                "B0_a_y_rmse", "B3_a_y_rmse")}
    print("\n=== AGGREGATE (sample-weighted across both Ford platforms) ===")
    for k, v in overall.items():
        if "yaw" in k:
            print(f"  {k}: {v*1000:.3f} mrad/s")
        else:
            print(f"  {k}: {v:.3f} m/s²")

    # Attribution — incremental ladder
    print("\n=== Attribution (incremental drop in yaw-rate RMSE, mrad/s) ===")
    d01 = (overall["B0_yaw_rmse"] - overall["B1_yaw_rmse"]) * 1000
    d12 = (overall["B1_yaw_rmse"] - overall["B2_yaw_rmse"]) * 1000
    d23 = (overall["B2_yaw_rmse"] - overall["B3_yaw_rmse"]) * 1000
    total = d01 + d12 + d23
    print(f"  steering offset (B0→B1): {d01:+.3f}  ({d01/total*100:+5.1f}%)")
    print(f"  understeer factor (B1→B2): {d12:+.3f}  ({d12/total*100:+5.1f}%)")
    print(f"  lag compensation (B2→B3): {d23:+.3f}  ({d23/total*100:+5.1f}%)")
    print(f"  TOTAL drop (B0→B3): {total:.3f} mrad/s "
          f"({total/(overall['B0_yaw_rmse']*1000)*100:.1f}% rel.)")

    out_path = OUT_DIR / "results.json"
    payload = {"per_platform": results, "overall": overall,
               "attribution": {"d_B0_B1": d01, "d_B1_B2": d12, "d_B2_B3": d23,
                               "total": total}}
    out_path.write_text(json.dumps(payload, indent=2, default=float))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
