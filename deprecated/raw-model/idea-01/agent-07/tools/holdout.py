"""Sanity check: are V2/V3 per-platform fits stable on a held-out split?

Split segments randomly 70/30 per platform. Fit gain k and Kus on TRAIN segs
only; evaluate RMS on TEST segs. V1 (per-seg bias) is per-segment so it's
trivially "training" on each segment — we still apply it (in production you'd
estimate it from the first ~30 s of a drive).
"""
from __future__ import annotations
import glob, os, json, random
import numpy as np, pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-01/agent-07/data/sim/segments"
PLATFORMS = ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1")
L_BY_PLAT = {"FORD_MUSTANG_MACH_E_MK1": 2.984, "FORD_F_150_LIGHTNING_MK1": 3.70}

def rms(x):
    x = np.asarray(x, dtype=float); x = x[np.isfinite(x)]
    return float(np.sqrt(np.mean(x**2))) if len(x) else float("nan")

def load_one(c):
    df = pd.read_csv(c); df["__seg"] = c; return df

def per_seg_bias(g, L):
    v = g["v_mps"].values; d = g["delta_road_rad"].values; y = g["yaw_rate_meas_rads"].values
    a = (v / L) * (1.0/np.cos(d))**2
    r0 = y - (v/L)*np.tan(d)
    denom = float(np.dot(a, a))
    return float(-np.dot(a, r0)/denom) if denom > 1e-9 else 0.0

random.seed(0)
results = {}
for plat in PLATFORMS:
    L = L_BY_PLAT[plat]
    csvs = sorted(glob.glob(os.path.join(ROOT, plat, "*", "*", "*", "sim.csv")))
    random.shuffle(csvs)
    n_train = int(0.7 * len(csvs))
    train_c, test_c = csvs[:n_train], csvs[n_train:]
    train = pd.concat([load_one(c) for c in train_c], ignore_index=True)
    test  = pd.concat([load_one(c) for c in test_c],  ignore_index=True)

    # Per-seg bias (fit on each seg of train, plus each seg of test)
    biases_test = {seg: per_seg_bias(g, L) for seg, g in test.groupby("__seg")}
    biases_train = {seg: per_seg_bias(g, L) for seg, g in train.groupby("__seg")}

    # Build V1 train prediction (with train biases)
    def build_v1(df, biases):
        out = np.zeros(len(df))
        for seg, g in df.groupby("__seg"):
            idx = g.index.values
            d = g["delta_road_rad"].values - biases[seg]
            out[idx] = (g["v_mps"].values / L) * np.tan(d)
        return out

    p1_train = build_v1(train, biases_train)
    y_train  = train["yaw_rate_meas_rads"].values
    k = float(np.dot(p1_train, y_train) / np.dot(p1_train, p1_train))

    # Kus fit on train at V2 level
    v_tr = train["v_mps"].values
    tan_de_tr = (k * p1_train * L) / np.maximum(v_tr, 1e-3)
    rhs = v_tr * tan_de_tr - y_train * L
    basis = y_train * v_tr * v_tr
    Kus = float(np.dot(basis, rhs) / np.dot(basis, basis))

    # Evaluate on test
    p1_test = build_v1(test, biases_test)
    y_test  = test["yaw_rate_meas_rads"].values
    v_te = test["v_mps"].values
    p0_test = test["yaw_rate_pred_rads"].values

    p2_test = k * p1_test
    tan_de_te = (p2_test * L) / np.maximum(v_te, 1e-3)
    p3_test = v_te * tan_de_te / (L + Kus * v_te * v_te)

    print(f"\n=== {plat}  (test {len(test_c)} segs, {len(test):,} samples) ===")
    print(f"  V0 (baseline KS)      RMS: {np.degrees(rms(y_test - p0_test)):.4f} deg/s")
    print(f"  V1 (+ per-seg bias)   RMS: {np.degrees(rms(y_test - p1_test)):.4f} deg/s")
    print(f"  V2 (+ gain k={k:.4f})    RMS: {np.degrees(rms(y_test - p2_test)):.4f} deg/s")
    print(f"  V3 (+ Kus={Kus:.5f})  RMS: {np.degrees(rms(y_test - p3_test)):.4f} deg/s")
    results[plat] = {"k": k, "Kus": Kus,
                     "V0": np.degrees(rms(y_test - p0_test)),
                     "V1": np.degrees(rms(y_test - p1_test)),
                     "V2": np.degrees(rms(y_test - p2_test)),
                     "V3": np.degrees(rms(y_test - p3_test))}

with open("out/holdout_results.json", "w") as f:
    json.dump(results, f, indent=2)
print("\nWrote out/holdout_results.json")
