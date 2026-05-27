"""Shapley-style attribution: average marginal RMSE drop over all orderings.

Three layers (A,B,C):
  A: steering-offset correction (delta_0)
  B: understeer factor K
  C: lag compensation (sample shift)

We evaluate all 2^3 = 8 coalitions and compute each layer's average marginal
contribution to RMSE reduction (vs. baseline B0 with none of the layers on).
"""
from __future__ import annotations

import json
from itertools import permutations, chain, combinations
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
AGENT_DIR = HERE.parent
DATA_DIR = AGENT_DIR / "data" / "sim" / "segments"
OUT_DIR = AGENT_DIR / "out"

PLATFORMS = ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]
L_BY = {"FORD_MUSTANG_MACH_E_MK1": 2.984, "FORD_F_150_LIGHTNING_MK1": 3.70}


def load_all():
    parts = []
    for plat in PLATFORMS:
        for p in sorted((DATA_DIR / plat).rglob("sim.csv")):
            df = pd.read_csv(p)
            cols = ["t_s", "v_mps", "delta_road_rad",
                    "yaw_rate_meas_rads", "yaw_rate_pred_rads", "a_lat_meas_mps2"]
            if not all(c in df.columns for c in cols):
                continue
            sub = df[cols].dropna()
            sub = sub[(sub["v_mps"] > 1.0) & (sub["a_lat_meas_mps2"].abs() < 20.0)]
            if len(sub) < 50:
                continue
            sub = sub.copy()
            sub["L"] = L_BY[plat]
            sub["seg_id"] = f"{plat}/{p.parent.relative_to(DATA_DIR/plat)}"
            parts.append(sub)
    return pd.concat(parts, ignore_index=True)


def shift_per_seg(arr: np.ndarray, seg_ids: np.ndarray, lag: int) -> np.ndarray:
    """Per-seg integer-sample shift; positive lag = move pred earlier."""
    out = arr.copy()
    # find seg boundaries
    boundaries = [0]
    for i in range(1, len(seg_ids)):
        if seg_ids[i] != seg_ids[i - 1]:
            boundaries.append(i)
    boundaries.append(len(seg_ids))
    for k in range(len(boundaries) - 1):
        a, b = boundaries[k], boundaries[k + 1]
        block = arr[a:b]
        if lag == 0:
            continue
        if lag > 0:
            new = np.empty_like(block)
            new[:-lag] = block[lag:]
            new[-lag:] = block[-1]
            out[a:b] = new
        else:
            kk = -lag
            new = np.empty_like(block)
            new[kk:] = block[:-kk]
            new[:kk] = block[0]
            out[a:b] = new
    return out


def predict(df, use_A: bool, use_B: bool, use_C: bool, params):
    L = df["L"].to_numpy()
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    if use_A:
        delta = delta - params["delta_off"]
    yr = (v / L) * np.tan(delta)
    if use_B:
        yr = yr / (1.0 + params["K"] * v * v)
    if use_C:
        yr = shift_per_seg(yr, df["seg_id"].to_numpy(), params["lag"])
    return yr


def rmse(a, b):
    return float(np.sqrt(np.mean((a - b) ** 2)))


def main():
    df = load_all()
    print(f"loaded rows={len(df):,} segments={df['seg_id'].nunique()}")
    y_meas = df["yaw_rate_meas_rads"].to_numpy()

    # Use the params we already fit in improve_lateral.py — they happen to be
    # platform-agnostic at this scale. Aggregate over both platforms.
    # Fit them quickly here for the combined set.
    L = df["L"].to_numpy()
    v = df["v_mps"].to_numpy()
    delta0 = df["delta_road_rad"].to_numpy()
    base = (v / L) * np.tan(delta0)
    # delta offset on combined
    d_grid = np.linspace(-0.01, 0.01, 81)
    best = min(d_grid, key=lambda d: np.mean(((v/L)*np.tan(delta0-d) - y_meas)**2))
    d_off = float(best)
    # K on combined, with offset on
    base_off = (v / L) * np.tan(delta0 - d_off)
    K_grid = np.linspace(-0.002, 0.005, 351)
    K_best = min(K_grid, key=lambda K: np.mean((base_off/(1+K*v*v) - y_meas)**2))
    K = float(K_best)
    # lag on combined with both
    pred_AB = base_off / (1.0 + K * v * v)
    lag_best = 0
    rbest = np.mean((pred_AB - y_meas)**2)
    for lag in range(-10, 11):
        shifted = shift_per_seg(pred_AB, df["seg_id"].to_numpy(), lag)
        r = np.mean((shifted - y_meas)**2)
        if r < rbest:
            rbest = r; lag_best = lag
    lag = int(lag_best)
    params = {"delta_off": d_off, "K": K, "lag": lag}
    print(f"  fit: delta_off={np.degrees(d_off):+.3f}°  K={K:+.5f}  lag={lag} samples ({lag*20:+d} ms)")

    layers = ["A", "B", "C"]
    coalition_rmse = {}
    for use_A in (False, True):
        for use_B in (False, True):
            for use_C in (False, True):
                yr = predict(df, use_A, use_B, use_C, params)
                r = rmse(yr, y_meas)
                key = ("A" if use_A else "") + ("B" if use_B else "") + ("C" if use_C else "")
                key = key or "∅"
                coalition_rmse[key] = r

    print("\nCoalition RMSE (mrad/s):")
    for k in ["∅","A","B","C","AB","AC","BC","ABC"]:
        print(f"  {k:>4}: {coalition_rmse[k]*1000:.3f}")

    # Shapley value = average over all orderings of marginal RMSE-drop contribution.
    def v_of(coal: set[str]) -> float:
        """RMSE drop relative to empty coalition."""
        key = "".join(sorted(coal)) or "∅"
        return coalition_rmse["∅"] - coalition_rmse[key]

    shapley = {}
    for player in layers:
        total = 0.0
        count = 0
        for perm in permutations(layers):
            idx = perm.index(player)
            before = set(perm[:idx])
            after = before | {player}
            total += v_of(after) - v_of(before)
            count += 1
        shapley[player] = total / count

    names = {"A": "steering offset (δ₀)",
             "B": "understeer factor (K)",
             "C": "lag compensation"}
    print("\nShapley attribution of RMSE reduction (mrad/s):")
    total_shap = sum(shapley.values())
    for p in layers:
        s = shapley[p] * 1000
        print(f"  {names[p]:30s}: {s:+.3f}  ({s/(total_shap*1000)*100:+5.1f}%)")
    print(f"  TOTAL  drop (full-vs-empty)   : {total_shap*1000:.3f} mrad/s "
          f"({total_shap/coalition_rmse['∅']*100:.1f}% rel.)")

    out_path = OUT_DIR / "shapley.json"
    out_path.write_text(json.dumps({
        "params": params,
        "coalition_rmse": coalition_rmse,
        "shapley_mrad_per_s": {k: v*1000 for k, v in shapley.items()},
    }, indent=2, default=float))
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
