"""Diagnose V1 residuals — look for structure vs delta_dot, a_long, v, |delta|."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v2/agent-10")
sys.path.insert(0, str(ROOT / "code"))
from v1_baseline import predict_v1

DATA_SIM = ROOT / "data" / "sim" / "segments"


def iter_csvs(platform, limit=80):
    plat_dir = DATA_SIM / platform
    out = []
    for route_dir in sorted(plat_dir.iterdir()):
        if not route_dir.is_dir():
            continue
        for sub in sorted(route_dir.iterdir()):
            if not sub.is_dir():
                continue
            for seg in sorted(sub.iterdir()):
                f = seg / "sim.csv"
                if f.is_file():
                    out.append(f)
                if len(out) >= limit:
                    return out
    return out


def diag(platform, limit=80):
    rows = []
    for f in iter_csvs(platform, limit=limit):
        df = pd.read_csv(f)
        # build sim_df-like
        sim_in = pd.DataFrame(index=df.index)
        for c in ["t_s", "delta_wheel_deg", "delta_road_rad", "v_mps", "a_long_mps2",
                  "accel_pedal_pct", "brake_pressed", "yaw_rate_pred_rads"]:
            sim_in[c] = df[c].to_numpy() if c in df.columns else 0.0
        pred = predict_v1(sim_in, platform)["yaw_rate_pred_rads"].to_numpy()
        truth = df["yaw_rate_meas_rads"].to_numpy()
        resid = truth - pred
        # features
        t = df["t_s"].to_numpy()
        dt = np.diff(t, prepend=t[0])
        delta = df["delta_road_rad"].to_numpy()
        ddelta_dt = np.gradient(delta, t)
        a_long = df["a_long_mps2"].to_numpy()
        v = df["v_mps"].to_numpy()
        rows.append({
            "resid": resid, "v": v, "delta": delta, "ddelta_dt": ddelta_dt,
            "a_long": a_long, "pred": pred, "truth": truth,
        })
    R = np.concatenate([r["resid"] for r in rows])
    V = np.concatenate([r["v"] for r in rows])
    D = np.concatenate([r["delta"] for r in rows])
    DD = np.concatenate([r["ddelta_dt"] for r in rows])
    AL = np.concatenate([r["a_long"] for r in rows])
    P = np.concatenate([r["pred"] for r in rows])
    T = np.concatenate([r["truth"] for r in rows])
    print(f"=== {platform} (n_seg={len(rows)}, n_samples={len(R)}) ===")
    print(f"resid mean={R.mean():.5f}  std={R.std():.5f}  rmse={np.sqrt((R**2).mean()):.5f}")
    print(f"truth std={T.std():.5f}  pred std={P.std():.5f}  pearson={np.corrcoef(P,T)[0,1]:.4f}")
    # correlation of residual with features
    for name, X in [("v", V), ("delta", D), ("ddelta_dt", DD), ("a_long", AL),
                    ("|delta|", np.abs(D)), ("v*delta", V*D), ("v^2*delta", V*V*D),
                    ("v*ddelta", V*DD), ("pred", P)]:
        if X.std() > 1e-12:
            corr = np.corrcoef(R, X)[0, 1]
            print(f"  corr(resid, {name:>12s}) = {corr:+.4f}")
    # Linear regression resid ~ ddelta_dt and resid ~ v*ddelta_dt
    for feats, names in [([V*DD], ["v*ddelta"]), ([DD], ["ddelta"]),
                          ([V*DD, V*V*D], ["v*ddelta", "v2delta"]),
                          ([DD, V*DD], ["ddelta", "v*ddelta"])]:
        X = np.column_stack(feats)
        # least squares with bias
        Xb = np.column_stack([X, np.ones(len(X))])
        beta, *_ = np.linalg.lstsq(Xb, R, rcond=None)
        fit = Xb @ beta
        rmse_after = np.sqrt(((R - fit) ** 2).mean())
        print(f"  fit {names} -> beta={beta[:-1]} bias={beta[-1]:.5e} rmse_after={rmse_after:.5f}")


for p in ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]:
    diag(p, limit=80)
