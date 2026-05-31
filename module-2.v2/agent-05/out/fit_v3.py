"""V3: extend feature basis further."""
from __future__ import annotations
import sys, os, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-05")
os.chdir(ROOT)

PLATFORM_TRUTH = {
    "FORD_F_150_LIGHTNING_MK1": "yaw_rate_meas_rads",
    "FORD_MUSTANG_MACH_E_MK1":  "yaw_rate_meas_rads",
    "HYUNDAI_IONIQ_5":          "yaw_rate_meas_rads",
}
V_FILTER = 2.0

def list_segments(plat):
    return sorted((ROOT / "data" / "sim" / "segments" / plat).glob("*/**/sim.csv"))

def build_feats(df):
    yv0 = df["yaw_rate_pred_rads"].to_numpy(float)
    v   = df["v_mps"].to_numpy(float)
    d   = df["delta_road_rad"].to_numpy(float)
    t   = df["t_s"].to_numpy(float)
    if "steer_rate_dps" in df.columns:
        sr = df["steer_rate_dps"].to_numpy(float) * np.pi / 180.0
    else:
        sr = np.gradient(d, t) if len(t) > 1 else np.zeros_like(d)
    a_long = df.get("a_long_mps2", pd.Series(np.zeros(len(df)))).to_numpy(float)
    return {
        "yv0": yv0,
        "v": v,
        "d": d,
        "vd": v * d,
        "v2d": v * v * d,
        "d3": d ** 3,
        "vd3": v * d ** 3,
        "v2d3": v * v * d ** 3,
        "sr": sr,
        "vsr": v * sr,
        "d_abs_d": d * np.abs(d),
        "a_long": a_long,
    }

FEATURES = ["yv0","v","d","vd","v2d","d3","vd3","v2d3","sr","vsr","d_abs_d","a_long"]

def fit_platform(plat):
    truth_col = PLATFORM_TRUTH[plat]
    Xs, ys = [], []
    for p in list_segments(plat):
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        if "yaw_rate_pred_rads" not in df.columns:
            continue
        v = df["v_mps"].to_numpy(float)
        mask = v > V_FILTER
        if not mask.any():
            continue
        f = build_feats(df)
        cols = [f[name][mask] for name in FEATURES]
        cols.append(np.ones(mask.sum()))
        X = np.column_stack(cols)
        yt = df[truth_col].to_numpy(float)[mask]
        Xs.append(X); ys.append(yt)
    X = np.vstack(Xs); y = np.concatenate(ys)
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    d = {name: float(coef[i]) for i, name in enumerate(FEATURES + ["intercept"])}
    d["n_samples"] = int(len(y))
    return d

if __name__ == "__main__":
    coeffs = {}
    for plat in PLATFORM_TRUTH:
        res = fit_platform(plat)
        print(f"{plat}: {res}")
        coeffs[plat] = res
    coeffs["TESLA_MODEL_3"] = None
    out = ROOT / "out" / "v3_coeffs.json"
    out.write_text(json.dumps(coeffs, indent=2))
    print(f"Wrote {out}")
