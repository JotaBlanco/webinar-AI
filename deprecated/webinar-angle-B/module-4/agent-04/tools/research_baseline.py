"""Phase 1 (Research): load all Ford sim CSVs, compute V0 baseline and sign-sanity.

Outputs: out/baseline.json (counts, per-regime RMSE on yaw_rate_resid_rads as-is).
"""
from __future__ import annotations
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA_SIM = ROOT / "data" / "sim" / "segments"
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

PLATFORMS = ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]

def load_platform(platform: str) -> pd.DataFrame:
    paths = sorted((DATA_SIM / platform).rglob("sim.csv"))
    dfs = []
    for i, p in enumerate(paths):
        try:
            df = pd.read_csv(p)
        except Exception as e:
            print(f"skip {p}: {e}", file=sys.stderr)
            continue
        df["seg_id"] = str(p.relative_to(DATA_SIM / platform).parent)
        df["platform"] = platform
        dfs.append(df)
    if not dfs:
        return pd.DataFrame()
    return pd.concat(dfs, ignore_index=True)

def regime_mask(df: pd.DataFrame) -> pd.Series:
    d = df["delta_road_rad"].abs()
    # derivative of delta
    ddelta = df.groupby("seg_id")["delta_road_rad"].diff().fillna(0.0) / 0.02
    ddelta = ddelta.abs()
    r = pd.Series(index=df.index, dtype="object")
    r[:] = "straight"
    r[(d >= 0.01) & (ddelta < 0.05)] = "steady"
    r[(d >= 0.01) & (ddelta >= 0.05)] = "transient"
    return r

def rmse(x: np.ndarray) -> float:
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return float("nan")
    return float(np.sqrt(np.mean(x * x)))

def main():
    results = {}
    for platform in PLATFORMS:
        df = load_platform(platform)
        if df.empty:
            results[platform] = {"n_segments": 0, "n_samples": 0}
            continue
        df["regime"] = regime_mask(df)
        # sign sanity on cornering
        corner = df[df["delta_road_rad"].abs() >= 0.01]
        sign_corr = float(np.corrcoef(corner["delta_road_rad"], corner["yaw_rate_meas_rads"])[0, 1]) if len(corner) > 1 else float("nan")
        v0 = df["yaw_rate_resid_rads"].to_numpy()
        per_regime = {}
        for reg in ("straight", "steady", "transient"):
            mask = df["regime"] == reg
            per_regime[reg] = {"n": int(mask.sum()), "rmse": rmse(v0[mask.to_numpy()])}
        results[platform] = {
            "n_segments": int(df["seg_id"].nunique()),
            "n_samples": int(len(df)),
            "rmse_overall_v0": rmse(v0),
            "sign_corr_delta_yawrate": sign_corr,
            "per_regime": per_regime,
            "mean_yawrate_resid": float(np.nanmean(v0)),
            "mean_a_y_pred": float(np.nanmean(df["a_y_pred_mps2"])),
            "max_abs_a_y_meas": float(np.nanmax(np.abs(df["a_lat_meas_mps2"]))),
        }
    with open(OUT / "baseline.json", "w") as f:
        json.dump(results, f, indent=2)
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
