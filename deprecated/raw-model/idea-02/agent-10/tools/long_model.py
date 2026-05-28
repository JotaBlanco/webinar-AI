"""Longitudinal-speed model — predicts v(t) from driver-commanded inputs.

Goal: remove the crutch where the vehicle model treats measured longitudinal
speed as an input. We predict a_long from (accel pedal, brake, current v),
then integrate to get v. Validation is closed-loop on Ford segments
(which expose ApedPos + brake-pressed + measured a_long).

Model form (per platform, linear in features, fit on train, tested on holdout):
    a_pred(t) = k_th * aped(t)           # tractive term
               + k_br * brake(t)         # brake decel (negative weight)
               + k_drag * v(t)           # linear drag + rolling resistance
               + k_regen * lift_off(t)   # one-pedal regen
               + b                       # bias/grade-mean
where lift_off = 1 when aped==0 and brake==0 (coast/regen regime).
This is a coarse but interpretable physics-shaped regression.

Baseline: a_pred = const mean(a_long) — equivalent to "no model".
Also report: a_pred = measured a_long (perfect-input ceiling) — what current
KS implicitly uses via its v-clamp; it's the cheat we're removing.

Metric: closed-loop integrated-speed RMSE (m/s) over the segment, plus MAE.
Regime breakdown: cruise / accel / brake / coast by labelling each timestep.
"""
from __future__ import annotations

import csv
import glob
import os
from pathlib import Path
from typing import Iterable

import numpy as np

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-10")
SIM = ROOT / "data" / "sim" / "segments"
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)


def load_segment(csv_path: Path) -> dict:
    """Load one sim.csv -> dict of numpy arrays for the columns we need.

    Brake handling: Ford has `brake_pressed` (0/1); Tesla's
    `brake_pedal_state` is a constant enum (the openpilot DBC doesn't decode
    a useful brake-pressed signal from the party DBC). For Tesla we instead
    use `di_torque_actual_nm` (motor torque, negative = regen/braking) which
    captures both drive and brake-via-regen in one continuous signal."""
    import pandas as pd
    df = pd.read_csv(csv_path)
    need_core = ["t_s", "v_mps", "a_long_mps2", "accel_pedal_pct"]
    if not all(c in df.columns for c in need_core):
        return None
    if "brake_pressed" in df.columns:
        brk = df["brake_pressed"].to_numpy().astype(float)
        torque = None
    elif "di_torque_actual_nm" in df.columns:
        # Tesla path: brake_pedal_state is unusable, use motor torque sign.
        torque = df["di_torque_actual_nm"].to_numpy()
        brk = (torque < -50.0).astype(float)  # strong regen ~ braking
    else:
        return None
    return {
        "t":    df["t_s"].to_numpy(),
        "v":    df["v_mps"].to_numpy(),
        "a":    df["a_long_mps2"].to_numpy(),
        "aped": df["accel_pedal_pct"].to_numpy(),
        "brk":  brk,
        "torque": torque,
        "name": str(csv_path.relative_to(SIM)),
    }


def build_features(seg: dict) -> np.ndarray:
    """Return N x 6 feature matrix: [aped, brake, v, v^2, liftoff, torque_norm].

    `v^2` captures aero drag (quadratic in v). `torque_norm` is added when
    motor-torque data is available (Tesla); otherwise it's zero, leaving the
    model effectively 5-feature."""
    aped = seg["aped"] / 100.0   # 0..1
    brk = seg["brk"].astype(float)
    v = seg["v"]
    liftoff = ((seg["aped"] <= 0.5) & (brk < 0.5)).astype(float)
    bias = np.ones_like(v)
    if seg.get("torque") is not None:
        tq = seg["torque"] / 1000.0   # roughly normalize
    else:
        tq = np.zeros_like(v)
    return np.column_stack([aped, brk, v, v*v, liftoff, tq, bias])


def fit_model(segs: list[dict]):
    X = np.concatenate([build_features(s) for s in segs])
    y = np.concatenate([s["a"] for s in segs])
    # Least squares.
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    return coef


def predict_a(seg: dict, coef: np.ndarray) -> np.ndarray:
    return build_features(seg) @ coef


def integrate_v(t: np.ndarray, a: np.ndarray, v0: float) -> np.ndarray:
    """Forward-Euler integration of a(t) starting from v0."""
    v = np.empty_like(a)
    v[0] = v0
    dt = np.diff(t)
    for i in range(1, len(a)):
        v[i] = v[i-1] + a[i-1] * dt[i-1]
        if v[i] < 0:
            v[i] = 0.0
    return v


def closed_loop_rmse(seg: dict, coef: np.ndarray) -> dict:
    """Closed-loop: predict a from (aped, brake, *predicted-v*, liftoff)."""
    aped = seg["aped"] / 100.0
    brk = seg["brk"].astype(float)
    liftoff = ((seg["aped"] <= 0.5) & (brk < 0.5)).astype(float)
    tq = (seg["torque"] / 1000.0) if seg.get("torque") is not None else np.zeros_like(seg["v"])
    t = seg["t"]
    v_true = seg["v"]
    v_pred = np.empty_like(v_true)
    a_pred = np.empty_like(v_true)
    v_pred[0] = v_true[0]
    for i in range(len(t)):
        feats = np.array([aped[i], brk[i], v_pred[i], v_pred[i]**2,
                          liftoff[i], tq[i], 1.0])
        a_pred[i] = feats @ coef
        if i + 1 < len(t):
            dt = t[i+1] - t[i]
            v_pred[i+1] = max(0.0, v_pred[i] + a_pred[i] * dt)
    err = v_pred - v_true
    return {
        "v_pred": v_pred,
        "a_pred": a_pred,
        "err": err,
        "rmse": float(np.sqrt(np.mean(err**2))),
        "mae":  float(np.mean(np.abs(err))),
        "max":  float(np.max(np.abs(err))),
    }


def regime_labels(seg: dict) -> np.ndarray:
    """Label each timestep by measured a_long & pedal: 0=cruise, 1=accel,
    2=brake/decel, 3=coast. We use the measured a_long as the primary
    discriminator because Tesla's brake_pedal_state is unusable."""
    a = seg["a"]
    aped = seg["aped"]
    lab = np.zeros(len(a), dtype=int)               # default cruise
    lab[(a > 0.5) & (aped > 5)] = 1                  # accel
    lab[a < -0.5] = 2                                # decel/brake (any cause)
    lab[(np.abs(a) <= 0.5) & (aped <= 5)] = 3        # coast
    return lab


def regime_breakdown(err: np.ndarray, labels: np.ndarray) -> dict:
    names = {0: "cruise", 1: "accel", 2: "brake", 3: "coast"}
    out = {}
    for k, name in names.items():
        m = labels == k
        if m.sum() > 0:
            out[name] = {
                "n":   int(m.sum()),
                "rmse": float(np.sqrt(np.mean(err[m]**2))),
                "mae":  float(np.mean(np.abs(err[m]))),
            }
        else:
            out[name] = {"n": 0, "rmse": float("nan"), "mae": float("nan")}
    return out


def baseline_constant(segs: list[dict]) -> float:
    """Mean a_long across all data — 'no-model' baseline accel."""
    a = np.concatenate([s["a"] for s in segs])
    return float(np.mean(a))


def baseline_constant_rmse(seg: dict, a_const: float) -> dict:
    """Integrate v with constant a_const; compute closed-loop RMSE."""
    t = seg["t"]
    v_true = seg["v"]
    v_pred = np.empty_like(v_true)
    v_pred[0] = v_true[0]
    for i in range(1, len(t)):
        v_pred[i] = max(0.0, v_pred[i-1] + a_const * (t[i] - t[i-1]))
    err = v_pred - v_true
    return {
        "v_pred": v_pred, "err": err,
        "rmse": float(np.sqrt(np.mean(err**2))),
        "mae":  float(np.mean(np.abs(err))),
    }


def ceiling_measured_a_rmse(seg: dict) -> dict:
    """Use measured a_long itself as the 'prediction' — what KS currently
    implicitly does via v-clamp. This is the unattainable upper bound."""
    t = seg["t"]
    v_true = seg["v"]
    v_pred = integrate_v(t, seg["a"], v_true[0])
    err = v_pred - v_true
    return {
        "rmse": float(np.sqrt(np.mean(err**2))),
        "mae":  float(np.mean(np.abs(err))),
    }


def collect_platform(platform: str, max_segments: int = 60) -> list[dict]:
    paths = sorted(glob.glob(str(SIM / platform / "**" / "sim.csv"), recursive=True))
    segs = []
    for p in paths[:max_segments]:
        try:
            s = load_segment(Path(p))
            if s is None:
                continue
            if len(s["t"]) < 100:
                continue
            # Drop segments with NaN/inf or unreasonable spikes in core channels.
            arrs = [s["t"], s["v"], s["a"], s["aped"], s["brk"]]
            if any(not np.all(np.isfinite(a)) for a in arrs):
                continue
            if np.max(np.abs(s["a"])) > 30.0:   # |a| > 3g is bogus
                continue
            if np.max(s["v"]) > 60.0:           # >216 km/h is bogus for these vehicles
                continue
            segs.append(s)
        except Exception:
            continue
    return segs


def run_platform(platform: str):
    print(f"\n=== {platform} ===")
    all_segs = collect_platform(platform, max_segments=80)
    if not all_segs:
        print(f"  no segments with required columns; skipping")
        return None
    print(f"  loaded {len(all_segs)} segments")

    # Hash-based train/test split (60/40).
    train = [s for s in all_segs if hash(s["name"]) % 5 < 3]
    test  = [s for s in all_segs if hash(s["name"]) % 5 >= 3]
    if not train or not test:
        # fallback halving
        train, test = all_segs[::2], all_segs[1::2]
    print(f"  train={len(train)}  test={len(test)}")

    coef = fit_model(train)
    a_const = baseline_constant(train)
    print(f"  coef [aped, brake, v, v^2, liftoff, torque, bias] = {coef.round(4).tolist()}")
    print(f"  baseline constant-a (mean) = {a_const:.4f} m/s²")

    # Open-loop one-step accel error on test set (no integration).
    X_te = np.concatenate([build_features(s) for s in test])
    y_te = np.concatenate([s["a"] for s in test])
    yp_te = X_te @ coef
    ol_rmse = float(np.sqrt(np.mean((y_te - yp_te) ** 2)))
    ol_mae  = float(np.mean(np.abs(y_te - yp_te)))
    a_std   = float(y_te.std())
    print(f"  open-loop one-step a_long: RMSE={ol_rmse:.4f}  MAE={ol_mae:.4f}  "
          f"(vs measured-a std {a_std:.4f}; skill={1.0 - ol_rmse/a_std:.2%})")

    # Aggregate across test set, weighted by length.
    agg = {"model": [], "baseline": [], "ceiling": []}
    regime_acc = {name: {"err2_sum": 0.0, "abs_sum": 0.0, "n": 0}
                  for name in ("cruise", "accel", "brake", "coast")}
    for s in test:
        r = closed_loop_rmse(s, coef)
        b = baseline_constant_rmse(s, a_const)
        c = ceiling_measured_a_rmse(s)
        agg["model"].append((r["rmse"], r["mae"], len(s["t"])))
        agg["baseline"].append((b["rmse"], b["mae"], len(s["t"])))
        agg["ceiling"].append((c["rmse"], c["mae"], len(s["t"])))
        labs = regime_labels(s)
        rb = regime_breakdown(r["err"], labs)
        for name, d in rb.items():
            if d["n"] > 0:
                regime_acc[name]["err2_sum"] += d["rmse"]**2 * d["n"]
                regime_acc[name]["abs_sum"]  += d["mae"]  * d["n"]
                regime_acc[name]["n"]        += d["n"]

    def pooled(rows):
        ns = np.array([r[2] for r in rows], dtype=float)
        rmse2 = np.array([r[0]**2 for r in rows])
        mae = np.array([r[1] for r in rows])
        w = ns / ns.sum()
        return float(np.sqrt((rmse2 * w).sum())), float((mae * w).sum())

    m_rmse, m_mae = pooled(agg["model"])
    b_rmse, b_mae = pooled(agg["baseline"])
    c_rmse, c_mae = pooled(agg["ceiling"])

    print(f"  closed-loop, pooled across {len(test)} test segments:")
    print(f"    BASELINE (const-a):    RMSE={b_rmse:6.3f} m/s   MAE={b_mae:6.3f} m/s")
    print(f"    MODEL (linear regr.):  RMSE={m_rmse:6.3f} m/s   MAE={m_mae:6.3f} m/s")
    print(f"    CEILING (meas a_long): RMSE={c_rmse:6.3f} m/s   MAE={c_mae:6.3f} m/s")
    print(f"  regime breakdown (model):")
    for name, d in regime_acc.items():
        if d["n"] > 0:
            rmse = (d["err2_sum"] / d["n"]) ** 0.5
            mae = d["abs_sum"] / d["n"]
            print(f"    {name:7s}: n={d['n']:6d}  RMSE={rmse:6.3f} m/s  MAE={mae:6.3f} m/s")
        else:
            print(f"    {name:7s}: n=0")

    return {
        "platform": platform,
        "coef": coef.tolist(),
        "baseline_rmse": b_rmse, "baseline_mae": b_mae,
        "model_rmse": m_rmse,    "model_mae": m_mae,
        "ceiling_rmse": c_rmse,  "ceiling_mae": c_mae,
        "regime": regime_acc,
        "n_train": len(train), "n_test": len(test),
    }


def main():
    results = {}
    for plat in ("FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1", "TESLA_MODEL_3"):
        r = run_platform(plat)
        if r is not None:
            results[plat] = r

    # Write summary CSV.
    with open(OUT / "long_model_summary.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["platform", "n_train", "n_test",
                    "baseline_rmse", "model_rmse", "ceiling_rmse",
                    "baseline_mae",  "model_mae",  "ceiling_mae"])
        for p, r in results.items():
            w.writerow([p, r["n_train"], r["n_test"],
                        f"{r['baseline_rmse']:.4f}", f"{r['model_rmse']:.4f}", f"{r['ceiling_rmse']:.4f}",
                        f"{r['baseline_mae']:.4f}",  f"{r['model_mae']:.4f}",  f"{r['ceiling_mae']:.4f}"])
    print(f"\nwrote {OUT/'long_model_summary.csv'}")


if __name__ == "__main__":
    main()
