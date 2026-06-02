"""Fit per-platform bias correction AND a ridge residual-learner head on V1's residual.

Phase A: compute pooled per-platform bias from V1 residual (yaw_truth - yaw_v1_pred).
Phase B: subtract bias, fit a small ridge model on remaining residual using
allowlist-derived features only (no truth-derived inputs).

Train on a route-split train fold, validate on dev fold to pick lambda.
Save coeffs to JSON used by final-model/predict.py.
"""
import sys, json, importlib.util, hashlib
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-05")

spec = importlib.util.spec_from_file_location("v1_baseline", ROOT / "code" / "v1_baseline.py")
v1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(v1)

DATA = ROOT / "data" / "sim" / "segments"
PLATS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]

def load_segment(path: Path) -> tuple[pd.DataFrame, str, str]:
    """Return (df, platform, route_id) for a segment csv."""
    parts = path.parts
    # .../segments/<PLATFORM>/<ROUTE>/<...>/sim.csv
    idx = parts.index("segments")
    platform = parts[idx+1]
    route = parts[idx+2]
    df = pd.read_csv(path)
    return df, platform, route


def build_features(sim_df: pd.DataFrame, yr_v1: np.ndarray) -> np.ndarray:
    """Construct residual-learner features from allowlist + v1 pred only.
    Keep small and physics-flavoured: yaw, |yaw|, lat accel proxy, steering, dsteer/dt,
    speed, abs steering * speed, brake, accel pedal.
    """
    t = sim_df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    dt[dt <= 0] = 0.02
    v = sim_df["v_mps"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    a_long = sim_df["a_long_mps2"].to_numpy() if "a_long_mps2" in sim_df.columns else np.zeros_like(v)
    brake = sim_df["brake_pressed"].to_numpy().astype(float) if "brake_pressed" in sim_df.columns else np.zeros_like(v)
    accel = (sim_df["accel_pedal_pct"].to_numpy() / 100.0) if "accel_pedal_pct" in sim_df.columns else np.zeros_like(v)

    # lateral accel proxy from V1
    a_lat_proxy = v * yr_v1
    # steering rate
    dd = np.gradient(delta, t)
    # yaw_dot proxy
    ydot = np.gradient(yr_v1, t)

    feats = np.column_stack([
        yr_v1,
        np.abs(yr_v1),
        a_lat_proxy,
        delta,
        np.abs(delta),
        dd,
        np.abs(dd),
        v,
        v * delta,
        v * yr_v1,
        a_long,
        brake,
        accel,
        ydot,
    ])
    # replace nans/infs
    feats = np.nan_to_num(feats, nan=0.0, posinf=0.0, neginf=0.0)
    return feats


FEATURE_NAMES = [
    "yr_v1","abs_yr_v1","a_lat_proxy","delta","abs_delta","dd","abs_dd",
    "v","v_delta","v_yr","a_long","brake","accel","ydot",
]


def main():
    segs = sorted(DATA.rglob("sim.csv"))
    # exclude Tesla (no truth)
    segs = [p for p in segs if "TESLA_MODEL_3" not in p.parts]
    print(f"segments: {len(segs)}")

    # Train/dev split per-platform 80/20 by segment-path hash (so all platforms appear in both).
    def fold_of(seg_id: str) -> int:
        h = int(hashlib.md5(seg_id.encode()).hexdigest(), 16)
        return h % 5  # 5-fold; we'll use folds 0..3 = train, fold 4 = dev

    # Collect per-platform arrays
    by_plat = {plat: {"X_tr": [], "r_tr": [], "X_dv": [], "r_dv": [], "yr_v1_dv": [], "yr_truth_dv": []} for plat in PLATS}

    for sp in segs:
        df, plat, route = load_segment(sp)
        if plat not in PLATS: continue
        if "yaw_rate_meas_rads" not in df.columns: continue
        # Get V1 prediction
        try:
            v1_out = v1.predict_v1(df, plat)
        except Exception as e:
            continue
        yr_v1 = v1_out["yaw_rate_pred_rads"].to_numpy()
        yr_truth = df["yaw_rate_meas_rads"].to_numpy()
        resid = yr_truth - yr_v1

        v = df["v_mps"].to_numpy()
        mask = v > 2.0  # match scoring v-filter
        if mask.sum() < 10: continue

        X = build_features(df, yr_v1)
        fold = fold_of(str(sp))
        if fold < 4:
            by_plat[plat]["X_tr"].append(X[mask])
            by_plat[plat]["r_tr"].append(resid[mask])
        else:
            by_plat[plat]["X_dv"].append(X[mask])
            by_plat[plat]["r_dv"].append(resid[mask])

    # Stack
    out_coeffs = {"feature_names": FEATURE_NAMES, "platforms": {}}
    for plat in PLATS:
        d = by_plat[plat]
        X_tr = np.vstack(d["X_tr"]) if d["X_tr"] else np.zeros((0, len(FEATURE_NAMES)))
        r_tr = np.concatenate(d["r_tr"]) if d["r_tr"] else np.zeros(0)
        X_dv = np.vstack(d["X_dv"]) if d["X_dv"] else np.zeros((0, len(FEATURE_NAMES)))
        r_dv = np.concatenate(d["r_dv"]) if d["r_dv"] else np.zeros(0)
        print(f"\n=== {plat} ===")
        print(f"  train samples: {len(r_tr)}, dev samples: {len(r_dv)}")

        # Per-platform bias = mean over BOTH train and dev (more robust when one fold dominates).
        # Recall sign: resid = yr_truth - yr_v1. Score uses (pred - truth), so we subtract this from pred.
        # i.e. new_pred = v1_pred + bias  (bias positive => v1 was underpredicting).
        all_r = np.concatenate([r_tr, r_dv]) if (len(r_tr)+len(r_dv))>0 else np.zeros(1)
        bias = float(np.mean(all_r))
        print(f"  fitted bias (all-data): {bias:.6f}")

        # Detrend residual: y = resid - bias
        y_tr = r_tr - bias
        y_dv = r_dv - bias

        # Standardise features by train stats
        mu = X_tr.mean(axis=0)
        sd = X_tr.std(axis=0); sd[sd < 1e-9] = 1.0
        Z_tr = (X_tr - mu) / sd
        Z_dv = (X_dv - mu) / sd

        # Ridge: pick lambda from grid
        best = None
        for lam in [1e0, 1e1, 3e1, 1e2, 3e2, 1e3, 3e3, 1e4]:
            # Solve (Z'Z + lam I) w = Z'y
            A = Z_tr.T @ Z_tr + lam * np.eye(Z_tr.shape[1])
            b = Z_tr.T @ y_tr
            w = np.linalg.solve(A, b)
            yhat_dv = Z_dv @ w
            # Score: residual-RMSE on dev relative to bias-only
            rmse_bias_only = float(np.sqrt(np.mean(y_dv**2))) if len(y_dv) else 0.0
            rmse_with = float(np.sqrt(np.mean((y_dv - yhat_dv)**2))) if len(y_dv) else 0.0
            if best is None or rmse_with < best["rmse_with"]:
                best = {"lam": lam, "w": w.tolist(), "rmse_bias_only": rmse_bias_only, "rmse_with": rmse_with}
        print(f"  bias-only dev resid RMSE: {best['rmse_bias_only']:.6f}")
        print(f"  ridge dev resid RMSE:     {best['rmse_with']:.6f}  (lam={best['lam']})")

        out_coeffs["platforms"][plat] = {
            "bias": bias,
            "ridge_lambda": best["lam"],
            "ridge_w": best["w"],
            "feature_mu": mu.tolist(),
            "feature_sd": sd.tolist(),
            "n_train": int(len(r_tr)),
            "n_dev": int(len(r_dv)),
            "dev_resid_rmse_bias_only": best["rmse_bias_only"],
            "dev_resid_rmse_ridge":     best["rmse_with"],
        }

    OUT = ROOT / "final-model" / "coeffs.json"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out_coeffs, indent=2))
    print(f"\nwrote {OUT}")

if __name__ == "__main__":
    main()
