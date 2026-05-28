#!/usr/bin/env python3
"""ablate_lateral.py — V0 → V1 → V2 → V3 ladder for lateral yaw-rate fidelity.

Implements the discipline in skills/ablation-study/SKILL.md:
- single fixed segment set + regime mask (matches baseline-residual)
- interleaved every-5th-sample train/test split (test = i%5==0)
- additive monotone variants in locked order
- strict marginal RMSE attribution + coherence check
- per-regime breakdown
- per-platform fits, not per-segment

Usage:  python3 tools/ablate_lateral.py <PLATFORM>

Writes CSV+JSON under out/ablate_<PLATFORM>_<ts>.{csv,json}.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REGIME_DELTA_THR = 0.01
REGIME_DDELTA_THR = 0.05


def regime_mask(df: pd.DataFrame) -> np.ndarray:
    delta = df["delta_road_rad"].to_numpy()
    t = df["t_s"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt <= 0, 0.02, dt)
    ddelta = np.gradient(delta) / dt
    out = np.full(len(df), "transient", dtype=object)
    out[np.abs(delta) < REGIME_DELTA_THR] = "straight"
    steady = (np.abs(delta) >= REGIME_DELTA_THR) & (np.abs(ddelta) < REGIME_DDELTA_THR)
    out[steady] = "steady"
    return out


def rmse(arr) -> float:
    s = np.asarray(arr, dtype=float)
    s = s[np.isfinite(s)]
    return float(np.sqrt(np.mean(s ** 2))) if s.size else float("nan")


def load_platform(platform: str) -> pd.DataFrame:
    root = Path("data/sim/segments") / platform
    csvs = sorted(root.rglob("sim.csv"))
    if not csvs:
        raise SystemExit(f"no sim.csv under {root}")
    frames = []
    for i, p in enumerate(csvs):
        df = pd.read_csv(p, usecols=[
            "t_s", "delta_road_rad", "v_mps",
            "yaw_rate_meas_rads", "yaw_rate_pred_rads",
        ])
        # per-segment lag shift uses contiguous block boundaries; tag with seg id
        df["__seg__"] = i
        frames.append(df)
    big = pd.concat(frames, ignore_index=True)
    print(f"loaded {len(csvs)} segments, {len(big):,} samples")
    return big


def per_regime_rmse(resid: np.ndarray, reg: np.ndarray, mask: np.ndarray):
    out = {"overall": rmse(resid[mask])}
    for r in ("straight", "steady", "transient"):
        sel = mask & (reg == r)
        out[r] = rmse(resid[sel])
    return out


def main():
    if len(sys.argv) != 2:
        print("usage: ablate_lateral.py <PLATFORM>", file=sys.stderr)
        sys.exit(2)
    platform = sys.argv[1]
    big = load_platform(platform)

    meas = big["yaw_rate_meas_rads"].to_numpy()
    pred_v0 = big["yaw_rate_pred_rads"].to_numpy()
    reg = regime_mask(big)

    # interleaved split — every 5th sample is test
    idx = np.arange(len(big))
    test_mask = (idx % 5) == 0
    train_mask = ~test_mask

    results = []  # list of dicts: variant, params, train RMSE, test RMSE, per-regime test

    # V0
    resid0 = pred_v0 - meas
    v0_test = per_regime_rmse(resid0, reg, test_mask)
    v0_train = per_regime_rmse(resid0, reg, train_mask)
    results.append({
        "variant": "V0 baseline",
        "params": {},
        "test": v0_test,
        "train": v0_train,
    })

    # V1: bias removal — fit median(pred - meas) on TRAIN, subtract from pred
    bias = float(np.median((pred_v0 - meas)[train_mask]))
    pred_v1 = pred_v0 - bias
    resid1 = pred_v1 - meas
    v1_test = per_regime_rmse(resid1, reg, test_mask)
    v1_train = per_regime_rmse(resid1, reg, train_mask)
    results.append({
        "variant": "V1 +bias",
        "params": {"bias_rads": bias},
        "test": v1_test,
        "train": v1_train,
    })

    # V2: scalar gain — fit pred_v1 -> meas on TRAIN via least-squares,
    # solve g minimising sum((g*pred_v1 - meas)^2)  => g = (pred·meas)/(pred·pred)
    p = pred_v1[train_mask]
    m = meas[train_mask]
    gain = float(np.dot(p, m) / np.dot(p, p))
    pred_v2 = gain * pred_v1
    resid2 = pred_v2 - meas
    v2_test = per_regime_rmse(resid2, reg, test_mask)
    v2_train = per_regime_rmse(resid2, reg, train_mask)
    results.append({
        "variant": "V2 +gain",
        "params": {"bias_rads": bias, "gain": gain},
        "test": v2_test,
        "train": v2_train,
    })

    # V3: 1-sample lag alignment per segment (shift pred forward by 1 sample to
    # match meas which arrives ~20 ms later).  Done per-segment to avoid
    # cross-segment bleed.
    pred_v3 = np.empty_like(pred_v2)
    segs = big["__seg__"].to_numpy()
    starts = np.r_[0, np.where(np.diff(segs) != 0)[0] + 1, len(segs)]
    for a, b in zip(starts[:-1], starts[1:]):
        block = pred_v2[a:b]
        if len(block) >= 2:
            shifted = np.empty_like(block)
            shifted[:-1] = block[1:]
            shifted[-1] = block[-1]
            pred_v3[a:b] = shifted
        else:
            pred_v3[a:b] = block
    resid3 = pred_v3 - meas
    v3_test = per_regime_rmse(resid3, reg, test_mask)
    v3_train = per_regime_rmse(resid3, reg, train_mask)
    results.append({
        "variant": "V3 +lag1",
        "params": {"bias_rads": bias, "gain": gain, "lag_samples": 1},
        "test": v3_test,
        "train": v3_train,
    })

    # Marginal attribution on test overall
    print(f"\nPlatform: {platform}")
    print(f"Train/Test split: every 5th sample → test ({test_mask.sum():,} test, {train_mask.sum():,} train)")
    print()
    header = f"{'variant':<14s} {'overall':>9s} {'Δ(marg)':>9s} {'straight':>9s} {'steady':>9s} {'transient':>10s}"
    print(header)
    prev = None
    rows = []
    for r in results:
        cur = r["test"]["overall"]
        marg = (prev - cur) if prev is not None else 0.0
        prev = cur
        flag = "  REGRESSION" if marg < 0 and r["variant"] != "V0 baseline" else ""
        line = (f"{r['variant']:<14s} {cur:9.5f} {marg:+9.5f} "
                f"{r['test']['straight']:9.5f} {r['test']['steady']:9.5f} "
                f"{r['test']['transient']:10.5f}{flag}")
        print(line)
        rows.append({
            "variant": r["variant"],
            "test_overall": cur,
            "test_straight": r["test"]["straight"],
            "test_steady": r["test"]["steady"],
            "test_transient": r["test"]["transient"],
            "marginal": marg,
            "params": json.dumps(r["params"]),
        })

    total = results[0]["test"]["overall"] - results[-1]["test"]["overall"]
    summed = sum(r["marginal"] for r in rows if r["variant"] != "V0 baseline")
    coherence = abs(summed - total) / abs(total) if total else float("nan")
    print()
    print(f"Total drop (V0→V3): {total:+.5f} rad/s ({100*total/results[0]['test']['overall']:.1f}% of V0)")
    print(f"Sum of marginals:   {summed:+.5f}")
    print(f"Attribution coherence: {coherence:.4f}  (must be < 0.15)")

    ts = time.strftime("%Y%m%d-%H%M%S")
    outdir = Path("out")
    outdir.mkdir(exist_ok=True)
    csv_path = outdir / f"ablate_{platform}_{ts}.csv"
    json_path = outdir / f"ablate_{platform}_{ts}.json"
    pd.DataFrame(rows).to_csv(csv_path, index=False)
    with open(json_path, "w") as f:
        json.dump({
            "platform": platform,
            "n_samples": int(len(big)),
            "rows": rows,
            "total_drop": total,
            "sum_marginals": summed,
            "attribution_coherence": coherence,
        }, f, indent=2)
    print(f"\nwrote {csv_path}")
    print(f"wrote {json_path}")


if __name__ == "__main__":
    main()
