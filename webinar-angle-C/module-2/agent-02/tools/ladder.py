"""Lateral fidelity variant ladder.

Platform: FORD_MUSTANG_MACH_E_MK1 (per-platform fit).
Truth: yaw_rate_meas_rads (measured by Ford IMU, decodable on Ford).
Residual sign convention: pred - meas (rule 1).
Speed and steering are clamped (rule 5); only lateral states are free.

Variant ladder (strict marginal accounting, V0 -> V_last applied
cumulatively; each row shows incremental RMSE delta vs prior row):

  V0  baseline: yaw_rate_resid_rads as-is.
  V1  per-platform bias removal (median of (pred-meas) on Mach-E pool).
  V2  per-platform scalar gain k on yaw_rate_pred to minimise SSE on
      interleaved (every 5th sample) train split; evaluated on the
      held-out test split. The fit captures effective understeer +
      steer-ratio mismatch in one parameter.
  V3  per-platform integer lag alignment on yaw_rate_pred (search
      +/- 25 samples = +/- 0.5 s at 50 Hz; pick lag minimising train
      RMSE). Apply same lag at test.

a_y_pred is re-derived as v * yaw_rate_pred after each transform
(rule 9).
"""

import glob
import os
import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/module-2/agent-02"
PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
SIM = os.path.join(ROOT, "data/sim/segments", PLATFORM)

# regime thresholds (rad/s on |yaw_rate_meas|; m/s on |v|)
CORNER_TH = 0.05      # >= cornering
TRANSIENT_TH = 0.20   # rad/s^2 |d yaw_rate_meas / dt|


def load_segments():
    paths = sorted(glob.glob(os.path.join(SIM, "*/*/*/sim.csv")))
    dfs = []
    for p in paths:
        try:
            df = pd.read_csv(p)
        except Exception:
            continue
        need = {"t_s", "v_mps", "yaw_rate_meas_rads", "yaw_rate_pred_rads",
                "yaw_rate_resid_rads", "a_lat_meas_mps2"}
        if not need.issubset(df.columns):
            continue
        df = df.dropna(subset=list(need)).reset_index(drop=True)
        if len(df) < 200:
            continue
        seg_id = "/".join(p.split("/")[-4:-1])
        df["_seg"] = seg_id
        dfs.append(df)
    return pd.concat(dfs, ignore_index=True), len(dfs)


def regime_masks(df):
    ymeas = df["yaw_rate_meas_rads"].to_numpy()
    dt = np.gradient(df["t_s"].to_numpy())
    dydt = np.gradient(ymeas) / np.where(dt == 0, 1e-9, dt)
    abs_y = np.abs(ymeas)
    abs_dy = np.abs(dydt)
    straight = abs_y < CORNER_TH
    steady = (abs_y >= CORNER_TH) & (abs_dy < TRANSIENT_TH)
    transient = (abs_y >= CORNER_TH) & (abs_dy >= TRANSIENT_TH)
    return {"all": np.ones(len(df), bool),
            "straight": straight,
            "steady_corner": steady,
            "transient_corner": transient}


def rmse(x):
    x = x[np.isfinite(x)]
    return float(np.sqrt(np.mean(x ** 2))) if len(x) else float("nan")


def per_regime(resid, masks):
    return {k: rmse(resid[m]) for k, m in masks.items()}


def main():
    df, n_seg = load_segments()
    N = len(df)
    idx = np.arange(N)
    test_mask = (idx % 5 == 0)
    train_mask = ~test_mask

    ymeas = df["yaw_rate_meas_rads"].to_numpy()
    ypred0 = df["yaw_rate_pred_rads"].to_numpy()
    v = df["v_mps"].to_numpy()

    # ---- V0: baseline residual as-is
    r0 = (ypred0 - ymeas)
    masks_all = regime_masks(df)
    # restrict to test set for honest comparison
    test_masks = {k: m & test_mask for k, m in masks_all.items()}

    rows = []

    def score(name, ypred, note=""):
        resid = ypred - ymeas
        scores = per_regime(resid, test_masks)
        rows.append({"variant": name, "note": note, **scores})
        return resid

    r_v0 = score("V0_baseline", ypred0, "raw KS pred")

    # ---- V1: per-platform bias removal (median on TRAIN set)
    bias = float(np.median((ypred0 - ymeas)[train_mask]))
    ypred1 = ypred0 - bias
    r_v1 = score("V1_bias", ypred1, f"-{bias:+.5f} rad/s")

    # ---- V2: per-platform scalar gain on yaw_rate_pred (fit on TRAIN)
    # minimise sum (k*ypred1 - ymeas)^2 -> k = <ypred1, ymeas>/<ypred1, ypred1>
    yp1_tr = ypred1[train_mask]
    ym_tr = ymeas[train_mask]
    k = float(np.dot(yp1_tr, ym_tr) / np.dot(yp1_tr, yp1_tr))
    ypred2 = k * ypred1
    r_v2 = score("V2_gain", ypred2, f"k={k:.4f}")

    # ---- V3: integer lag alignment (search +/- 25 samples on TRAIN)
    best_lag, best_rmse = 0, float("inf")
    for lag in range(-25, 26):
        if lag >= 0:
            yp_shift = np.concatenate([np.full(lag, ypred2[0]), ypred2[:-lag]]) if lag > 0 else ypred2
        else:
            yp_shift = np.concatenate([ypred2[-lag:], np.full(-lag, ypred2[-1])])
        resid_tr = (yp_shift - ymeas)[train_mask]
        rms = rmse(resid_tr)
        if rms < best_rmse:
            best_rmse, best_lag = rms, lag
    lag = best_lag
    if lag > 0:
        ypred3 = np.concatenate([np.full(lag, ypred2[0]), ypred2[:-lag]])
    elif lag < 0:
        ypred3 = np.concatenate([ypred2[-lag:], np.full(-lag, ypred2[-1])])
    else:
        ypred3 = ypred2
    r_v3 = score("V3_lag", ypred3, f"lag={lag} samples ({lag*0.02:+.2f}s)")

    # ---- a_y consistency check on final variant (rule 9)
    a_y_pred_v3 = v * ypred3
    a_y_meas = df["a_lat_meas_mps2"].to_numpy()
    a_y_resid = (a_y_pred_v3 - a_y_meas)[test_mask]
    a_y_rmse = rmse(a_y_resid)

    # ---- report
    print(f"# Platform: {PLATFORM}")
    print(f"# Segments: {n_seg}  samples: {N}  test samples: {int(test_mask.sum())}")
    print(f"# Regime counts (test): "
          + ", ".join(f"{k}={int(m.sum())}" for k, m in test_masks.items()))
    print()
    print("variant            | all     straight steady   transient  | note")
    print("-" * 90)
    prev = None
    for row in rows:
        line = (f"{row['variant']:18s} | "
                f"{row['all']*1000:7.2f} "
                f"{row['straight']*1000:7.2f} "
                f"{row['steady_corner']*1000:7.2f} "
                f"{row['transient_corner']*1000:8.2f}   | {row['note']}")
        print(line)
    # marginal deltas on 'all'
    print()
    print("marginal improvements (all-regime RMSE, mrad/s):")
    for i in range(1, len(rows)):
        d = (rows[i-1]["all"] - rows[i]["all"]) * 1000
        print(f"  {rows[i-1]['variant']} -> {rows[i]['variant']}: {d:+.2f}")

    print()
    print(f"V3 fitted constants: bias={bias:+.5f} rad/s, gain k={k:.4f}, lag={lag} samples")
    print(f"V3 a_y test RMSE (rederived v*yaw_rate_pred): {a_y_rmse:.3f} m/s^2")

    # save csv of variants
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(ROOT, "out/ladder.csv"), index=False)


if __name__ == "__main__":
    main()
