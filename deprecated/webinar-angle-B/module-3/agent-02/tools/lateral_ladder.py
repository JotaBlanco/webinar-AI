"""Lateral fidelity variant ladder on Mach-E sim.csv set.

V0  KS as-shipped (yaw_rate_resid_rads).
V1  KS + per-segment straight-line yaw-rate bias removal (gyro offset).
V2  Linear single-track, prior C_alpha (steady-state gain).
V3  Linear ST, fit C_alpha (bounded 50-500 kN/rad), single global fit.
V4  V3 + Ridge residual learner on [v, |a_y|, |delta|, sign(ddelta/dt)],
    LOSO CV — out-of-fold predictions only.

All variants use the SAME segments, SAME regime mask. Marginal RMSE drops
accounted with greedy left-to-right order (named: "ladder-order marginal").
"""
import glob, os, json, sys
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-3/agent-02"
PLAT = "FORD_MUSTANG_MACH_E_MK1"
# Mach-E params (openpilot canonical, from sim-real-runtime skill)
L      = 2.984
m      = 2336.0
I_z    = 4879.05
l_f    = 1.313
l_r    = 1.671
Caf0   = 286_551.0
Car0   = 355_912.0

def load_all():
    files = sorted(glob.glob(f"{ROOT}/data/sim/segments/{PLAT}/*/*/*/sim.csv"))
    rows = []
    for f in files:
        try:
            d = pd.read_csv(f)
        except Exception:
            continue
        if len(d) < 100: continue
        d["seg"] = f
        rows.append(d)
    return rows

def regime(d):
    delta = d["delta_road_rad"].to_numpy()
    ddel = np.gradient(delta, 0.02)
    abs_d = np.abs(delta); abs_dd = np.abs(ddel)
    straight = abs_d < 0.01
    steady   = (abs_d >= 0.01) & (abs_dd < 0.05)
    trans    = (abs_d >= 0.01) & (abs_dd >= 0.05)
    return straight, steady, trans, ddel

def rmse(a):  return float(np.sqrt(np.mean(a**2)))

def st_yaw_rate(v, delta, Caf, Car):
    K_us = m * (l_r*Car - l_f*Caf) / (L**2 * Caf * Car)
    denom = (L * (1.0 + K_us * v**2))
    # sub-step / floor at low v
    out = np.where(v > 2.0, v*delta/denom, (v/L)*np.tan(delta))
    return out

def main():
    segs = load_all()
    print(f"# segments loaded: {len(segs)}", file=sys.stderr)

    # quick sign check on a subset
    big = pd.concat(segs, ignore_index=True)
    mask_corner = np.abs(big["delta_road_rad"]) >= 0.01
    c = np.corrcoef(big.loc[mask_corner,"delta_road_rad"], big.loc[mask_corner,"yaw_rate_meas_rads"])[0,1]
    print(f"sign-sanity corr(delta_road, yaw_meas | cornering) = {c:.3f}", file=sys.stderr)

    # accumulate per-row predictions across all variants
    all_rows = []
    for d in segs:
        v = d["v_mps"].to_numpy()
        delta = d["delta_road_rad"].to_numpy()
        y = d["yaw_rate_meas_rads"].to_numpy()
        a_y_meas = d["a_lat_meas_mps2"].to_numpy()
        yhat_ks = d["yaw_rate_pred_rads"].to_numpy()

        straight, steady, trans, ddel = regime(d)
        # V1: subtract per-seg mean residual on straight-line samples
        if straight.sum() > 50:
            bias = float(np.mean(yhat_ks[straight] - y[straight]))
        else:
            bias = 0.0
        yhat_v1 = yhat_ks - bias

        # V2: ST with prior C_alpha, then re-apply per-seg straight-line bias removal
        st_prior = st_yaw_rate(v, delta, Caf0, Car0)
        if straight.sum() > 50:
            bias2 = float(np.mean(st_prior[straight] - y[straight]))
        else:
            bias2 = 0.0
        yhat_v2 = st_prior - bias2

        df = pd.DataFrame({
            "seg": d["seg"].iloc[0],
            "v": v, "delta": delta, "a_y_meas": a_y_meas,
            "ddel": ddel,
            "y_meas": y,
            "v0": yhat_ks,
            "v1": yhat_v1,
            "v2": yhat_v2,
            "straight": straight,
            "steady": steady,
            "trans": trans,
        })
        all_rows.append(df)
    big = pd.concat(all_rows, ignore_index=True)

    # V3: fit Caf,Car globally to minimise yaw-rate MSE (bounded)
    from scipy.optimize import minimize
    # scale parameters so the optimiser sees O(1) inputs
    def loss(p):
        Caf, Car = p[0]*1e5, p[1]*1e5
        yhat = st_yaw_rate(big["v"].to_numpy(), big["delta"].to_numpy(), Caf, Car)
        return float(np.mean((yhat - big["y_meas"].to_numpy())**2))
    # try several starts, take best
    best = (np.inf, (Caf0/1e5, Car0/1e5))
    for x0 in [(Caf0/1e5, Car0/1e5), (1.5,1.5), (4.0,4.0), (1.0,4.0), (4.0,1.0), (2.5,2.5)]:
        r = minimize(loss, x0=x0, method="Nelder-Mead",
                     options={"xatol":1e-4,"fatol":1e-10,"maxiter":500})
        if r.fun < best[0]:
            best = (r.fun, tuple(r.x))
    Caf_hat, Car_hat = best[1][0]*1e5, best[1][1]*1e5
    # apply bounds
    Caf_hat = float(np.clip(Caf_hat, 50_000, 500_000))
    Car_hat = float(np.clip(Car_hat, 50_000, 500_000))
    pegged = (abs(Caf_hat-500_000)<1 or abs(Caf_hat-50_000)<1 or
              abs(Car_hat-500_000)<1 or abs(Car_hat-50_000)<1)
    v3_pred = st_yaw_rate(big["v"].to_numpy(), big["delta"].to_numpy(), Caf_hat, Car_hat)
    # apply per-seg straight-line bias removal to keep V3 stacked above V1's correction
    big["v3"] = v3_pred
    for s in big["seg"].unique():
        m_s = (big["seg"] == s).to_numpy()
        straight_s = big["straight"].to_numpy() & m_s
        if straight_s.sum() > 50:
            b = float(np.mean(v3_pred[straight_s] - big.loc[m_s,"y_meas"].to_numpy().mean()*0 - big["y_meas"].to_numpy()[straight_s]))
            big.loc[m_s, "v3"] = v3_pred[m_s] - b
    print(f"V3 fit: Caf={Caf_hat:.0f} Car={Car_hat:.0f}  pegged={pegged}", file=sys.stderr)

    # V4: Ridge residual learner on V3 residuals, LOSO CV
    feats = np.column_stack([
        big["v"].to_numpy(),
        np.abs(big["a_y_meas"].to_numpy()),
        np.abs(big["delta"].to_numpy()),
        np.sign(big["ddel"].to_numpy()),
    ])
    target = big["y_meas"].to_numpy() - big["v3"].to_numpy()  # learn the residual
    seg_ids = big["seg"].to_numpy()
    uniq = np.unique(seg_ids)
    y_correction = np.zeros_like(target)
    for s in uniq:
        te = seg_ids == s
        tr = ~te
        if tr.sum() < 100: continue
        mdl = Ridge(alpha=1.0)
        mdl.fit(feats[tr], target[tr])
        y_correction[te] = mdl.predict(feats[te])
    big["v4"] = big["v3"] + y_correction

    # ----- RMSE table -----
    variants = ["v0","v1","v2","v3","v4"]
    names = {
        "v0": "KS (baseline)",
        "v1": "KS + per-seg straight-line yaw bias",
        "v2": "Linear ST, prior C_alpha",
        "v3": "Linear ST, fit C_alpha (bounded)",
        "v4": "V3 + Ridge residual learner (LOSO)",
    }
    masks = {"all": np.ones(len(big),dtype=bool),
             "straight": big["straight"].to_numpy(),
             "steady":   big["steady"].to_numpy(),
             "trans":    big["trans"].to_numpy()}

    table = {}
    for v in variants:
        err = big[v].to_numpy() - big["y_meas"].to_numpy()
        row = {reg: rmse(err[mk]) for reg, mk in masks.items()}
        table[v] = row

    # marginal drop (ladder-order, on 'all')
    prev = None
    marg = {}
    for v in variants:
        cur = table[v]["all"]
        marg[v] = 0.0 if prev is None else prev - cur
        prev = cur

    total_drop = table["v0"]["all"] - table["v4"]["all"]
    sum_marg = sum(marg.values())
    consistent = abs(sum_marg - total_drop) / max(total_drop,1e-9) < 0.15

    print("\nVARIANT LADDER RESULTS (yaw-rate RMSE, rad/s)")
    print(f"{'Variant':<8}{'name':<42}{'all':>9}{'straight':>11}{'steady':>10}{'trans':>10}{'marg':>10}")
    for v in variants:
        r = table[v]
        print(f"{v:<8}{names[v][:40]:<42}{r['all']:>9.4f}{r['straight']:>11.4f}{r['steady']:>10.4f}{r['trans']:>10.4f}{marg[v]:>10.4f}")
    print(f"\nTotal V0->V4 drop = {total_drop:.4f}   sum(marginal) = {sum_marg:.4f}   within-15%? {consistent}")
    print(f"V3 fit: Caf_hat = {Caf_hat:.0f} N/rad   Car_hat = {Car_hat:.0f} N/rad   pegged={pegged}")
    print(f"sign-sanity corr(delta_road, yaw_meas | cornering) = {c:.3f}")

    out = {
        "platform": PLAT,
        "n_segments": int(len(segs)),
        "n_samples": int(len(big)),
        "table": table,
        "marginal_drop_ladder_order": marg,
        "total_drop_v0_v4": float(total_drop),
        "marginal_sum_within_15pct": bool(consistent),
        "V3_Caf_hat": float(Caf_hat),
        "V3_Car_hat": float(Car_hat),
        "V3_pegged": bool(pegged),
        "sign_sanity_corr": float(c),
    }
    with open(f"{ROOT}/out/ladder.json","w") as fh:
        json.dump(out, fh, indent=2)

if __name__ == "__main__":
    main()
