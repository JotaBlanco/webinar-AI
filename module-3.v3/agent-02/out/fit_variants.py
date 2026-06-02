"""Fit candidate per-platform corrections on top of V1."""
import sys, math, json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-3.v3/agent-02")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "out"))

from scoring import list_segments, load_pair, PLATFORMS, score_predict_fn, print_score
import v1_baseline


def gather_features(plat, max_segs=None):
    """Return arrays of features for fitting per platform."""
    yr_v1_all=[]; yr_truth_all=[]; v_all=[]; t_all=[]; delta_all=[]; segs=[]
    items = list_segments(plat)
    if max_segs:
        items = items[:max_segs]
    for rel,_ in items:
        si, st = load_pair(plat, rel)
        out = v1_baseline.predict_v1(si, plat)
        yr_v1 = out["yaw_rate_pred_rads"].to_numpy()
        yr_t = st["yaw_rate_meas_rads"].to_numpy()
        v = si["v_mps"].to_numpy()
        t = si["t_s"].to_numpy()
        d = si["delta_road_rad"].to_numpy()
        yr_v1_all.append(yr_v1); yr_truth_all.append(yr_t); v_all.append(v); t_all.append(t); delta_all.append(d)
        segs.append((rel, len(yr_v1)))
    return {
        "yr_v1": np.concatenate(yr_v1_all),
        "yr_truth": np.concatenate(yr_truth_all),
        "v": np.concatenate(v_all),
        "t": np.concatenate(t_all),
        "delta": np.concatenate(delta_all),
        "segs": segs,
    }


def fit_affine(yr_v1, yr_truth):
    """yr = a*yr_v1 + b. OLS."""
    A = np.column_stack([yr_v1, np.ones_like(yr_v1)])
    coef, *_ = np.linalg.lstsq(A, yr_truth, rcond=None)
    return float(coef[0]), float(coef[1])


def fit_saturation(yr_v1, yr_truth, v):
    """yr = a*yr_v1 + b + c * yr_v1 * (v*yr_v1)^2.
    Cubic saturation: at high |a_lat_proxy|, c<0 reduces yaw — for Mach-E we want yaw bigger (truth larger negative).
    Actually if residual = pred - truth < 0 at high a_lat for Mach-E, pred is too negative -> need to reduce |yr|.
    Let me re-examine: signed residual at Mach-E |a_lat|=3-5 is -0.012, meaning pred < truth.
    yr_v1 there is more negative than truth? or less negative? Let's just fit."""
    a_lat = v * yr_v1
    A = np.column_stack([yr_v1, np.ones_like(yr_v1), yr_v1 * a_lat * a_lat])
    coef, *_ = np.linalg.lstsq(A, yr_truth, rcond=None)
    return float(coef[0]), float(coef[1]), float(coef[2])


def fit_steering_rate(yr_v1, yr_truth, t, delta, segs):
    """yr = a*yr_v1 + b + c * ddelta_dt.
    ddelta_dt computed per-segment to avoid boundary issues."""
    ddelta = np.zeros_like(delta)
    idx = 0
    for _, n in segs:
        seg_t = t[idx:idx+n]
        seg_d = delta[idx:idx+n]
        dd = np.gradient(seg_d, seg_t)
        # clip to avoid spikes
        ddelta[idx:idx+n] = np.clip(dd, -2.0, 2.0)
        idx += n
    A = np.column_stack([yr_v1, np.ones_like(yr_v1), ddelta])
    coef, *_ = np.linalg.lstsq(A, yr_truth, rcond=None)
    return float(coef[0]), float(coef[1]), float(coef[2])


def fit_combined(yr_v1, yr_truth, v, t, delta, segs):
    """Combine all features: yr = a*yr_v1 + b + c*yr_v1*a_lat^2 + d*ddelta_dt."""
    a_lat = v * yr_v1
    ddelta = np.zeros_like(delta)
    idx = 0
    for _, n in segs:
        dd = np.gradient(delta[idx:idx+n], t[idx:idx+n])
        ddelta[idx:idx+n] = np.clip(dd, -2.0, 2.0)
        idx += n
    A = np.column_stack([yr_v1, np.ones_like(yr_v1), yr_v1 * a_lat * a_lat, ddelta])
    coef, *_ = np.linalg.lstsq(A, yr_truth, rcond=None)
    return {"a": float(coef[0]), "b": float(coef[1]), "c": float(coef[2]), "d": float(coef[3])}


if __name__ == "__main__":
    coeffs = {}
    for plat in PLATFORMS:
        print(f"\n--- Fitting {plat} ---")
        d = gather_features(plat)
        print(f"  n={len(d['yr_v1'])} samples across {len(d['segs'])} segs")
        a, b = fit_affine(d["yr_v1"], d["yr_truth"])
        print(f"  affine:       a={a:.5f}, b={b:+.5f}")
        a2, b2, c2 = fit_saturation(d["yr_v1"], d["yr_truth"], d["v"])
        print(f"  saturation:   a={a2:.5f}, b={b2:+.5f}, c={c2:+.5e}")
        a3, b3, c3 = fit_steering_rate(d["yr_v1"], d["yr_truth"], d["t"], d["delta"], d["segs"])
        print(f"  steering_rate: a={a3:.5f}, b={b3:+.5f}, c={c3:+.5e}")
        full = fit_combined(d["yr_v1"], d["yr_truth"], d["v"], d["t"], d["delta"], d["segs"])
        print(f"  combined:     {full}")
        coeffs[plat] = {"affine": {"a": a, "b": b},
                        "saturation": {"a": a2, "b": b2, "c": c2},
                        "steering_rate": {"a": a3, "b": b3, "c": c3},
                        "combined": full}
    (ROOT / "out" / "fitted_coeffs.json").write_text(json.dumps(coeffs, indent=2))
    print("\nSaved coeffs to out/fitted_coeffs.json")
