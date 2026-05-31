"""Fit per-platform yaw-rate correction. Train/val split. Save coefficients."""
import os, glob, json, random
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-06/data/sim/segments"
OUT = "/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-06/final-model"
os.makedirs(OUT, exist_ok=True)

PLATFORMS_TRUTH = ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1", "HYUNDAI_IONIQ_5"]
PARAMS_L = {
    "TESLA_MODEL_3":            2.875,
    "FORD_MUSTANG_MACH_E_MK1":  2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
    "HYUNDAI_IONIQ_5":          3.00,  # rough; let fit absorb
}

random.seed(42)
coeffs = {}

for p in PLATFORMS_TRUTH:
    paths = sorted(glob.glob(f"{ROOT}/{p}/*/*/*/sim.csv"))
    random.shuffle(paths)
    n_train = int(len(paths) * 0.8)
    train_paths = paths[:n_train]
    val_paths = paths[n_train:]

    def load(paths):
        cols = ["t_s","v_mps","delta_road_rad","yaw_rate_meas_rads","yaw_rate_pred_rads","a_long_mps2"]
        dfs = []
        for path in paths:
            d = pd.read_csv(path, usecols=lambda c: c in cols)
            if "yaw_rate_meas_rads" not in d.columns: continue
            dfs.append(d)
        return pd.concat(dfs, ignore_index=True)

    Dtr = load(train_paths)
    Dva = load(val_paths)

    L = PARAMS_L[p]

    def rmse(pred, y): return float(np.sqrt(np.mean((pred-y)**2)))

    # V0 baseline
    v0_train = rmse(Dtr.yaw_rate_pred_rads, Dtr.yaw_rate_meas_rads)
    v0_val   = rmse(Dva.yaw_rate_pred_rads, Dva.yaw_rate_meas_rads)

    # M1: scale fit on KS pred (basically Ackermann gain trim, handles steering ratio bias)
    ks_pred_tr = Dtr.v_mps/L * np.tan(Dtr.delta_road_rad)
    ks_pred_va = Dva.v_mps/L * np.tan(Dva.delta_road_rad)
    a_scale = float(np.sum(ks_pred_tr*Dtr.yaw_rate_meas_rads)/np.sum(ks_pred_tr**2))
    m1_tr = rmse(a_scale*ks_pred_tr, Dtr.yaw_rate_meas_rads)
    m1_va = rmse(a_scale*ks_pred_va, Dva.yaw_rate_meas_rads)

    # M2: understeer ψ̇ = v·δ/(L_eff + K_us·v²), fit (L_eff, K_us).
    def loss(params):
        L_eff, K_us = params
        pred = Dtr.v_mps * Dtr.delta_road_rad / (L_eff + K_us * Dtr.v_mps**2)
        return float(np.mean((pred - Dtr.yaw_rate_meas_rads)**2))
    res = minimize(loss, x0=[L, 0.005], method="Nelder-Mead", options=dict(xatol=1e-5, fatol=1e-9, maxiter=4000))
    L_eff, K_us = res.x
    pred_us_tr = Dtr.v_mps * Dtr.delta_road_rad / (L_eff + K_us * Dtr.v_mps**2)
    pred_us_va = Dva.v_mps * Dva.delta_road_rad / (L_eff + K_us * Dva.v_mps**2)
    m2_tr = rmse(pred_us_tr, Dtr.yaw_rate_meas_rads)
    m2_va = rmse(pred_us_va, Dva.yaw_rate_meas_rads)

    # M3: affine combo a*ks + b*delta + c
    Xtr = np.column_stack([ks_pred_tr, Dtr.delta_road_rad, np.ones(len(Dtr))])
    Xva = np.column_stack([ks_pred_va, Dva.delta_road_rad, np.ones(len(Dva))])
    coef, *_ = np.linalg.lstsq(Xtr, Dtr.yaw_rate_meas_rads, rcond=None)
    m3_tr = rmse(Xtr @ coef, Dtr.yaw_rate_meas_rads)
    m3_va = rmse(Xva @ coef, Dva.yaw_rate_meas_rads)

    # M4: pick whichever is best on val
    cands = {
        "V0": (v0_tr := v0_train, v0_val, "v0"),
        "M1_scale": (m1_tr, m1_va, dict(a=a_scale)),
        "M2_understeer": (m2_tr, m2_va, dict(L_eff=L_eff, K_us=K_us)),
        "M3_affine": (m3_tr, m3_va, dict(a=float(coef[0]), b=float(coef[1]), c=float(coef[2]))),
    }
    best_name = min(cands, key=lambda k: cands[k][1])
    print(f"\n=== {p}  (train rows={len(Dtr)}, val rows={len(Dva)}) ===")
    for nm,(tr,va,_) in cands.items():
        marker = " <-- best val" if nm==best_name else ""
        print(f"  {nm:14s}  train RMSE={tr:.5f}  val RMSE={va:.5f}{marker}")
    print(f"  L_eff={L_eff:.4f}  K_us={K_us:.5f}")
    coeffs[p] = dict(
        L=L,
        best=best_name,
        m1=dict(a=a_scale),
        m2=dict(L_eff=float(L_eff), K_us=float(K_us)),
        m3=dict(a=float(coef[0]), b=float(coef[1]), c=float(coef[2])),
        val_rmse=dict(V0=v0_val, M1=m1_va, M2=m2_va, M3=m3_va),
        train_rmse=dict(V0=v0_train, M1=m1_tr, M2=m2_tr, M3=m3_tr),
    )

# Tesla: no labeled data — borrow median understeer + median scale from other 3.
mean_Kus = float(np.mean([coeffs[p]["m2"]["K_us"] for p in PLATFORMS_TRUTH]))
mean_scale = float(np.mean([coeffs[p]["m1"]["a"] for p in PLATFORMS_TRUTH]))
coeffs["TESLA_MODEL_3"] = dict(
    L=PARAMS_L["TESLA_MODEL_3"],
    best="M2_understeer",
    m1=dict(a=mean_scale),
    m2=dict(L_eff=PARAMS_L["TESLA_MODEL_3"], K_us=mean_Kus),
    m3=dict(a=1.0, b=0.0, c=0.0),
    note="No truth in sim/ for Tesla — using mean K_us across labeled platforms.",
)
print(f"\nTesla fallback: L={PARAMS_L['TESLA_MODEL_3']}, K_us={mean_Kus:.5f}")

with open(f"{OUT}/coeffs.json","w") as f:
    json.dump(coeffs, f, indent=2)
print(f"\nwrote {OUT}/coeffs.json")
