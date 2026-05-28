"""Lateral fidelity ratchet: V0..V4 RMSE breakdown on yaw_rate residual.

Platform: FORD_MUSTANG_MACH_E_MK1 (lateral-truth-bearing).
Speed-known contract: v, delta clamped to measurement; only psi_dot is predicted.
"""

import sys, os, glob, json
import numpy as np
import pandas as pd

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-A/module-2/agent-04"
SIM_GLOB = os.path.join(ROOT, "data/sim/segments/FORD_MUSTANG_MACH_E_MK1/*/*/*/sim.csv")

# Mach-E params (locally redeclared since we can write only inside agent-04 and
# parameters.py lives in shared code we treat as read-only — but we can read it.
# We replicate the constants needed here for transparency.)
L_FORD = 2.984        # wheelbase [m]
I_S_FORD = 17.0       # steering ratio
M_FORD = 2336.0
L_F = 1.3130
L_R = 1.671
C_F = 286_551.0
C_R = 355_912.0
I_Z = 4879.05

DT = 0.02
FS = 50.0


def load_all():
    files = sorted(glob.glob(SIM_GLOB))
    dfs = []
    for f in files:
        try:
            df = pd.read_csv(f)
        except Exception:
            continue
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        df = df.copy()
        df["__seg__"] = f
        dfs.append(df)
    return files, dfs


def rmse(x):
    x = np.asarray(x, dtype=float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return np.nan
    return float(np.sqrt(np.mean(x * x)))


def regime_masks(df):
    """Three regimes based on |a_y_meas| and its rate of change."""
    a_y = df["a_lat_meas_mps2"].to_numpy()
    a_y_abs = np.abs(a_y)
    # derivative of a_y at 50 Hz
    da_y = np.gradient(a_y, DT)
    da_y_abs = np.abs(da_y)
    straight = a_y_abs < 0.5
    transient = (~straight) & (da_y_abs > 1.5)
    steady = (~straight) & (~transient)
    return {"straight": straight, "cornering_steady": steady,
            "cornering_transient": transient, "all": np.ones_like(a_y, dtype=bool)}


def compute_pred_v1(df):
    """V1: recompute psi_dot from clamped (v, delta_road) using KS analytic
    formula, but with low-pass smoothing of the steering signal to reflect
    real actuator lag / signal noise. Keeps speed-known contract.

    The CSV already has yaw_rate_pred_rads which is KS-clamped. V1 simply
    applies a one-pole low-pass to delta_road before recomputing psi_dot.
    """
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    # 1-pole IIR low-pass, tau ~= 80 ms (~2 Hz), reflects rack compliance + signal lag
    tau = 0.08
    alpha = DT / (tau + DT)
    delta_f = np.empty_like(delta)
    delta_f[0] = delta[0]
    for k in range(1, len(delta)):
        delta_f[k] = alpha * delta[k] + (1 - alpha) * delta_f[k - 1]
    psi_dot_pred = (v / L_FORD) * np.tan(delta_f)
    return psi_dot_pred


def compute_pred_v2(df, v1_pred):
    """V2: per-segment bias removal on the residual.

    Yaw-rate measurements drift; subtract a per-segment mean residual.
    Estimated only on straight regime to avoid leaking cornering bias.
    """
    meas = df["yaw_rate_meas_rads"].to_numpy()
    resid = v1_pred - meas
    masks = regime_masks(df)
    bias = np.nanmean(resid[masks["straight"]]) if masks["straight"].any() else 0.0
    return v1_pred - bias, bias


def compute_pred_v3(df, v2_pred):
    """V3: Linear single-track steady-state correction (understeer gradient).

    Bicycle steady-state: psi_dot = v / (L + K_us * v^2) * delta_road,
    where K_us = (m / L) * (l_r / C_f - l_f / C_r) [s^2/m].
    KS sets K_us = 0; ST embeds tyre force balance. Adds slip-dependent
    suppression of yaw-rate at high speed/cornering.
    """
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    # reuse the low-pass from V1 (already baked in conceptually); but recompute
    # from delta to ensure V3 builds on V2's bias removal not delta filter.
    tau = 0.08
    alpha = DT / (tau + DT)
    delta_f = np.empty_like(delta)
    delta_f[0] = delta[0]
    for k in range(1, len(delta)):
        delta_f[k] = alpha * delta[k] + (1 - alpha) * delta_f[k - 1]
    K_us = (M_FORD / L_FORD) * (L_R / C_F - L_F / C_R)
    psi_dot_st = (v / (L_FORD + K_us * v * v)) * delta_f
    # carry V2 bias forward
    meas = df["yaw_rate_meas_rads"].to_numpy()
    # estimate bias from straight on the ST signal
    resid = psi_dot_st - meas
    masks = regime_masks(df)
    bias = np.nanmean(resid[masks["straight"]]) if masks["straight"].any() else 0.0
    return psi_dot_st - bias


def aggregate(dfs, pred_fn):
    """Compute residuals across all segments; return arrays for masking."""
    all_resid = []
    all_a_y = []
    all_da_y = []
    for df in dfs:
        pred = pred_fn(df)
        meas = df["yaw_rate_meas_rads"].to_numpy()
        resid = pred - meas
        a_y = df["a_lat_meas_mps2"].to_numpy()
        da_y = np.gradient(a_y, DT)
        all_resid.append(resid)
        all_a_y.append(a_y)
        all_da_y.append(da_y)
    return (np.concatenate(all_resid), np.concatenate(all_a_y),
            np.concatenate(all_da_y))


def score(resid, a_y, da_y):
    a_y_abs = np.abs(a_y)
    da_y_abs = np.abs(da_y)
    straight = a_y_abs < 0.5
    transient = (~straight) & (da_y_abs > 1.5)
    steady = (~straight) & (~transient)
    return {
        "all": rmse(resid),
        "straight": rmse(resid[straight]),
        "cornering_steady": rmse(resid[steady]),
        "cornering_transient": rmse(resid[transient]),
        "n_total": int(len(resid)),
        "n_straight": int(straight.sum()),
        "n_steady": int(steady.sum()),
        "n_transient": int(transient.sum()),
    }


def main():
    files, dfs = load_all()
    print(f"Loaded {len(dfs)} segments")

    # V0: baseline = pre-computed yaw_rate_pred_rads as-is.
    def pred_v0(df):
        return df["yaw_rate_pred_rads"].to_numpy()

    # V1: low-pass on delta
    def pred_v1(df):
        return compute_pred_v1(df)

    # V2: V1 + per-seg straight-bias removal
    def pred_v2(df):
        v1 = compute_pred_v1(df)
        v2, _ = compute_pred_v2(df, v1)
        return v2

    # V3: V2 + per-segment scalar gain fit (least-squares cornering-only).
    # Tests whether KS systematically mis-scales yaw rate (effective wheelbase
    # or steering ratio off). Fit gain g such that g * v1_pred ≈ meas on
    # cornering rows; clip g to a sane band.
    def pred_v3(df):
        v1 = compute_pred_v1(df)
        v2, bias = compute_pred_v2(df, v1)
        meas = df["yaw_rate_meas_rads"].to_numpy()
        a_y = df["a_lat_meas_mps2"].to_numpy()
        corner = np.abs(a_y) >= 0.5
        if corner.sum() > 50:
            p = v2[corner]
            m = meas[corner]
            denom = float(np.sum(p * p))
            if denom > 1e-9:
                g = float(np.sum(p * m) / denom)
            else:
                g = 1.0
            g = max(0.7, min(1.5, g))
        else:
            g = 1.0
        return g * v2

    # V4: V3 + linear ST steady-state understeer correction (K_us).
    # K_us > 0 for this geometry => understeer (yaw suppression at high v).
    def pred_v4(df):
        v = df["v_mps"].to_numpy()
        delta = df["delta_road_rad"].to_numpy()
        tau = 0.08
        alpha = DT / (tau + DT)
        delta_f = np.empty_like(delta)
        delta_f[0] = delta[0]
        for k in range(1, len(delta)):
            delta_f[k] = alpha * delta[k] + (1 - alpha) * delta_f[k - 1]
        K_us = (M_FORD / L_FORD) * (L_R / C_F - L_F / C_R)
        pred = (v / (L_FORD + K_us * v * v)) * delta_f
        # then bias removal on straight
        meas = df["yaw_rate_meas_rads"].to_numpy()
        a_y = df["a_lat_meas_mps2"].to_numpy()
        straight = np.abs(a_y) < 0.5
        if straight.any():
            yb = float(np.nanmean((pred - meas)[straight]))
        else:
            yb = 0.0
        pred = pred - yb
        # gain fit on cornering
        corner = np.abs(a_y) >= 0.5
        if corner.sum() > 50:
            p = pred[corner]; m = meas[corner]
            denom = float(np.sum(p * p))
            g = float(np.sum(p * m) / denom) if denom > 1e-9 else 1.0
            g = max(0.7, min(1.5, g))
        else:
            g = 1.0
        return g * pred

    variants = [
        ("V0_baseline", pred_v0),
        ("V1_delta_lowpass", pred_v1),
        ("V2_bias_removed", pred_v2),
        ("V3_perseg_gain_fit", pred_v3),
        ("V4_ST_understeer_plus_gain", pred_v4),
    ]

    results = {}
    prev_all = None
    rows = []
    for name, fn in variants:
        r, a_y, da_y = aggregate(dfs, fn)
        sc = score(r, a_y, da_y)
        sc["variant"] = name
        sc["delta_all_vs_prev"] = (prev_all - sc["all"]) if prev_all is not None else 0.0
        prev_all = sc["all"]
        results[name] = sc
        rows.append(sc)
        print(name, sc)

    # marginal accounting (sequential / shapley-like sequential decomposition)
    out = {
        "n_segments": len(dfs),
        "platform": "FORD_MUSTANG_MACH_E_MK1",
        "results": results,
    }
    with open(os.path.join(ROOT, "out", "results.json"), "w") as f:
        json.dump(out, f, indent=2)
    pd.DataFrame(rows).to_csv(os.path.join(ROOT, "out", "results.csv"), index=False)
    print("\nWrote out/results.json and out/results.csv")


if __name__ == "__main__":
    main()
