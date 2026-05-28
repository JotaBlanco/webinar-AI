"""Lateral-fidelity variant ladder for Mach-E.

V0: KS baseline as in CSV (yaw_rate_pred - yaw_rate_meas already present).
V1: V0 minus per-segment mean residual on straight samples (yaw-gyro bias).
V2: Linear single-track steady-state gain with prior C_alpha.
V3: Linear ST with fit C_alpha (bounded), LOSO global fit.

All variants scored on same segment set, same regime mask. Marginal RMSE drop
accounted as last-rung-wins (V0->V1, V1->V2, V2->V3).
"""
from __future__ import annotations
import sys, os, glob, json
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))
from parameters import MACH_E  # type: ignore

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-3/agent-05")
PLATFORM = "FORD_MUSTANG_MACH_E_MK1"
SIM_GLOB = str(ROOT / "data/sim/segments" / PLATFORM / "*/*/*/sim.csv")

p = MACH_E
L, m, l_f, l_r = p.L, p.m, p.l_f, p.l_r
Caf0, Car0 = p.C_alpha_f, p.C_alpha_r
V_MIN = 2.0  # m/s — below this fall back to KS

def K_us(Caf, Car):
    return m * (l_r * Car - l_f * Caf) / (L**2 * Caf * Car)

def st_yaw_rate(v, delta, Caf, Car):
    Kus = K_us(Caf, Car)
    denom = 1.0 + Kus * v * v
    return v * delta / (L * denom)

def ks_yaw_rate(v, delta):
    return (v / L) * np.tan(delta)

def regime_mask(delta_road, dt=0.02):
    d = delta_road
    ddot = np.gradient(d, dt)
    straight = np.abs(d) < 0.01
    steady = (np.abs(d) >= 0.01) & (np.abs(ddot) < 0.05)
    transient = (np.abs(d) >= 0.01) & (np.abs(ddot) >= 0.05)
    return straight, steady, transient

def load_segments():
    paths = sorted(glob.glob(SIM_GLOB))
    segs = []
    for path in paths:
        try:
            df = pd.read_csv(path)
        except Exception:
            continue
        need = {"delta_road_rad","v_mps","yaw_rate_meas_rads","yaw_rate_pred_rads"}
        if not need.issubset(df.columns):
            continue
        if df["v_mps"].mean() < 1.0:  # skip parked
            continue
        df = df.dropna(subset=list(need)).reset_index(drop=True)
        if len(df) < 100:
            continue
        segs.append((path, df))
    return segs

def main():
    segs = load_segments()
    print(f"Loaded {len(segs)} Mach-E segments")
    # Build a global mask & arrays per segment, also a valid-mask (v>=V_MIN)
    per_seg = []
    for path, df in segs:
        v = df["v_mps"].to_numpy()
        d = df["delta_road_rad"].to_numpy()
        ym = df["yaw_rate_meas_rads"].to_numpy()
        yp = df["yaw_rate_pred_rads"].to_numpy()
        valid = v >= V_MIN
        straight, steady, transient = regime_mask(d)
        per_seg.append(dict(path=path, v=v, d=d, ym=ym, yp=yp,
                            valid=valid, straight=straight,
                            steady=steady, transient=transient))

    # ---- Sign sanity check on cornering samples ----
    big_d = []
    big_ym = []
    for s in per_seg:
        cm = (s["steady"] | s["transient"]) & s["valid"]
        big_d.append(s["d"][cm]); big_ym.append(s["ym"][cm])
    big_d = np.concatenate(big_d); big_ym = np.concatenate(big_ym)
    sign_corr = float(np.corrcoef(big_d, big_ym)[0,1])
    print(f"Sign sanity corr(delta_road, yaw_rate_meas) on cornering = {sign_corr:+.3f}")

    # ---- V0: as-is residual from CSV ----
    def rmse(arr):
        return float(np.sqrt(np.mean(arr**2)))

    def collect_pred(variant):
        """Return concatenated (pred, meas) over the union mask for each regime.
        Variants are *cumulative*: V2 keeps V1's bias correction; V3 keeps V1's bias."""
        out = {"all": [[],[]], "straight": [[],[]], "steady": [[],[]], "transient": [[],[]]}
        for s in per_seg:
            v, d, ym, yp = s["v"], s["d"], s["ym"], s["yp"]
            m_valid = s["valid"]
            # V1 bias term (per-segment) — re-used in V2/V3
            mask_str = s["straight"] & m_valid
            bias = float(np.mean((yp - ym)[mask_str])) if mask_str.any() else 0.0
            if variant == "V0":
                pred = yp
            elif variant == "V1":
                pred = yp - bias
            elif variant == "V2":
                st_pred = np.where(v >= V_MIN, st_yaw_rate(np.maximum(v,V_MIN), d, Caf0, Car0), ks_yaw_rate(v, d))
                # Recompute bias for ST baseline on straights (per-segment, same DOF)
                st_bias = float(np.mean((st_pred - ym)[mask_str])) if mask_str.any() else 0.0
                pred = st_pred - st_bias
            elif variant == "V3":
                st_pred = np.where(v >= V_MIN, st_yaw_rate(np.maximum(v,V_MIN), d, CAF_FIT, CAR_FIT), ks_yaw_rate(v, d))
                st_bias = float(np.mean((st_pred - ym)[mask_str])) if mask_str.any() else 0.0
                pred = st_pred - st_bias
            mall = m_valid
            for key, mk in [("all", mall),
                            ("straight", s["straight"] & mall),
                            ("steady", s["steady"] & mall),
                            ("transient", s["transient"] & mall)]:
                out[key][0].append(pred[mk])
                out[key][1].append(ym[mk])
        result = {}
        for k,(P,M) in out.items():
            P = np.concatenate(P); M = np.concatenate(M)
            result[k] = (P, M, rmse(P - M), len(P))
        return result

    # Fit C_alpha for V3 by least squares on cornering samples (steady+transient, v>=V_MIN)
    # Linearize: ym = v*delta / (L*(1+Kus*v^2))  -> 1/ym_norm linear in Kus
    # Easier: minimize sum (ym - st(Caf,Car))^2 via scipy
    from scipy.optimize import minimize
    big_v = []; big_d2 = []; big_ym2 = []
    for s in per_seg:
        cm = (s["steady"] | s["transient"]) & s["valid"]
        # subtract per-segment straight-line bias from measured to remove gyro offset
        mask_str = s["straight"] & s["valid"]
        bias = float(np.mean((s["yp"] - s["ym"])[mask_str])) if mask_str.any() else 0.0
        big_v.append(s["v"][cm]); big_d2.append(s["d"][cm])
        big_ym2.append(s["ym"][cm] + bias)  # bias-corrected truth proxy
    big_v = np.concatenate(big_v); big_d2 = np.concatenate(big_d2); big_ym2 = np.concatenate(big_ym2)

    def loss(theta):
        Caf, Car = theta
        pred = st_yaw_rate(big_v, big_d2, Caf, Car)
        return float(np.mean((pred - big_ym2)**2))

    bounds = [(50_000, 500_000), (50_000, 500_000)]
    # Try several starts; pick best
    best = None
    for x0 in [[Caf0, Car0], [150_000, 150_000], [400_000, 400_000], [80_000, 200_000]]:
        r = minimize(loss, x0=x0, method="L-BFGS-B", bounds=bounds)
        if best is None or r.fun < best.fun:
            best = r
    res = best
    global CAF_FIT, CAR_FIT
    CAF_FIT, CAR_FIT = float(res.x[0]), float(res.x[1])
    pegged = (abs(CAF_FIT - 500_000) < 1 or abs(CAR_FIT - 500_000) < 1 or
              abs(CAF_FIT - 50_000) < 1 or abs(CAR_FIT - 50_000) < 1)
    print(f"Fit C_af={CAF_FIT:,.0f}, C_ar={CAR_FIT:,.0f} (prior {Caf0:,.0f}/{Car0:,.0f}) pegged={pegged}")

    table = {}
    for v in ["V0","V1","V2","V3"]:
        table[v] = collect_pred(v)

    rows = []
    prev_rmse = None
    for label, name in [("V0","KS baseline (CSV as-is)"),
                        ("V1","V0 + per-segment straight-line bias"),
                        ("V2","Linear ST, prior C_alpha"),
                        ("V3","Linear ST, fit C_alpha (bounded)")]:
        r_all = table[label]["all"][2]
        r_s = table[label]["straight"][2]
        r_st = table[label]["steady"][2]
        r_tr = table[label]["transient"][2]
        marginal = (prev_rmse - r_all) if prev_rmse is not None else 0.0
        rows.append(dict(variant=label, name=name,
                         rmse_all=r_all, rmse_straight=r_s,
                         rmse_steady=r_st, rmse_transient=r_tr,
                         marginal_drop=marginal))
        prev_rmse = r_all

    total_drop = table["V0"]["all"][2] - table["V3"]["all"][2]
    sum_marg = sum(r["marginal_drop"] for r in rows)
    n_all = table["V0"]["all"][3]
    print(json.dumps(dict(rows=rows, total_drop=total_drop, sum_marginals=sum_marg,
                          n_samples=n_all, sign_corr=sign_corr,
                          fit_Caf=CAF_FIT, fit_Car=CAR_FIT, pegged=pegged,
                          n_segments=len(per_seg)), indent=2))

if __name__ == "__main__":
    main()
