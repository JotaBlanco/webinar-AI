"""Per-platform residual structure analysis: regress V1 residual against
candidate features to find the dominant missing term.
"""
import sys, glob
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import predict_v1  # noqa

def load(plat, limit=200):
    paths = sorted(glob.glob(str(ROOT / f"data/sim/segments/{plat}/*/*/*/sim.csv")))[:limit]
    rows = []
    for p in paths:
        df = pd.read_csv(p, usecols=["t_s","delta_road_rad","v_mps","yaw_rate_meas_rads","yaw_rate_pred_rads","a_long_mps2"])
        out = predict_v1(df, plat)
        v1 = out["yaw_rate_pred_rads"].to_numpy()
        yt = df["yaw_rate_meas_rads"].to_numpy()
        v  = df["v_mps"].to_numpy()
        dr = df["delta_road_rad"].to_numpy()
        t  = df["t_s"].to_numpy()
        al = df["a_long_mps2"].to_numpy()
        resid = yt - v1
        # mask
        mask = v > 2.0
        if mask.sum() < 50: continue
        dt = np.gradient(t)
        ddelta = np.gradient(dr, t)
        dv = np.gradient(v, t)
        ay_pred = v * v1
        rows.append(dict(
            resid=resid[mask],
            v=v[mask], dr=dr[mask], v1=v1[mask], ay_pred=ay_pred[mask],
            ddelta=ddelta[mask], dv=dv[mask], al=al[mask],
            yt=yt[mask],
        ))
    return rows

def report(plat):
    rows = load(plat)
    R = np.concatenate([r["resid"] for r in rows])
    V = np.concatenate([r["v"] for r in rows])
    DR = np.concatenate([r["dr"] for r in rows])
    V1 = np.concatenate([r["v1"] for r in rows])
    AY = np.concatenate([r["ay_pred"] for r in rows])
    DD = np.concatenate([r["ddelta"] for r in rows])
    DV = np.concatenate([r["dv"] for r in rows])
    AL = np.concatenate([r["al"] for r in rows])
    YT = np.concatenate([r["yt"] for r in rows])
    print(f"\n=== {plat}  N={len(R)} ===")
    print(f"  resid mean: {R.mean():.6f}  std: {R.std():.6f}")
    feats = {
        "v": V, "dr": DR, "v1_yr": V1, "ay_pred": AY,
        "ddelta": DD, "dv": DV, "al": AL,
        "v*dr": V*DR, "v*ay": V*AY, "ay^2": AY*AY,
        "ay*sign(ay)": AY*np.sign(AY),
        "v*ddelta": V*DD,
        "yr_truth_proxy": V1,  # for ref
    }
    for k, x in feats.items():
        c = np.corrcoef(x, R)[0,1]
        print(f"  corr(resid, {k:18s}) = {c:+.3f}")
    # Estimate coefficient if we add gain * ay_pred
    # resid ~ a * ay_pred + b
    A = np.column_stack([AY, np.ones_like(AY)])
    coef, *_ = np.linalg.lstsq(A, R, rcond=None)
    print(f"  best linear fit: resid ~ {coef[0]:+.5f} * ay_pred + {coef[1]:+.6f}")
    # Try resid ~ a*v + b
    A = np.column_stack([V, np.ones_like(V)])
    coef, *_ = np.linalg.lstsq(A, R, rcond=None)
    print(f"  best linear fit: resid ~ {coef[0]:+.6f} * v       + {coef[1]:+.6f}")
    # ay^2 / v scaling for tyre nonlinearity
    A = np.column_stack([AY*np.abs(AY), AY, np.ones_like(AY)])
    coef, *_ = np.linalg.lstsq(A, R, rcond=None)
    print(f"  best linear fit: resid ~ {coef[0]:+.6f}*|ay|*ay + {coef[1]:+.6f}*ay + {coef[2]:+.6f}")

for plat in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
    report(plat)
