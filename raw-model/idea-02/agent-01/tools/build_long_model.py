"""Build a longitudinal model that predicts v_mps from commanded inputs.

Goal: remove the measured-speed crutch from the vehicle model. We currently
clamp v_state to v_meas at every integration step (speed-known mode). This
script fits a longitudinal acceleration model that depends on driver
*commands* (accel pedal, brake pressed) and the model's own predicted speed
(through drag-like terms). Integrating this acceleration over a segment
yields v_pred(t) that stands on its own — no measured speed required.

Model form (per platform):
    a_pred(t) = c_thr * accel_pedal_pct
              + c_brk_on * brake_pressed
              + c_v   * v_pred
              + c_v2  * v_pred * |v_pred|
              + c_0

This is a coast-down style polynomial in v plus linear input gains. Fit by
ordinary least squares using measured a_long_mps2 as the target. We DO NOT
use v_mps in the regressor at training time — we use v_pred at evaluation
time. To keep the fit honest, we train against v_meas (since v_pred is
unknown during fit), accepting a small train/test bias.

Validation:
  Mode A — open-loop one-step (a-residual): RMSE of a_pred vs a_long_meas.
  Mode B — closed-loop integration: v_pred(t) = v0 + cumtrapz(a_pred(v_pred), dt)
           reported as RMSE(v_pred - v_meas) over the full segment.
  Mode C — baseline: v_pred(t) = v0 + cumtrapz(a_long_meas, dt). This is the
           "use the sensed acceleration" crutch — still uses sensed data, but
           illustrates pure integration drift.

Regimes are tagged from the measurement channels:
  cruise : |a|<0.3 m/s2 and speed>5 m/s
  accel  : a > 0.5
  brake  : a < -0.5 OR brake_pressed
  coast  : |a|<0.5 and accel_pedal_pct < 1
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-01")
DATA = ROOT / "data" / "sim" / "segments"
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

PLATFORMS = {
    "FORD_MUSTANG_MACH_E_MK1": {"pedal": "accel_pedal_pct", "brake": "brake_pressed"},
    "FORD_F_150_LIGHTNING_MK1": {"pedal": "accel_pedal_pct", "brake": "brake_pressed"},
    "TESLA_MODEL_3":            {"pedal": "accel_pedal_pct", "brake": "brake_pedal_state"},
}


def find_segs(platform: str) -> list[Path]:
    return sorted((DATA / platform).rglob("sim.csv"))


def load_seg(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    # Some signals may be missing or NaN; coerce
    for c in ("v_mps", "a_long_mps2"):
        if c not in df:
            return None
    df = df.dropna(subset=["t_s", "v_mps", "a_long_mps2"]).reset_index(drop=True)
    if len(df) < 100:
        return None
    # Outlier filter: drop segments with implausible a_long (>15 m/s2 sustained)
    if df["a_long_mps2"].abs().max() > 15:
        return None
    if df["v_mps"].max() > 60 or df["v_mps"].min() < -1:
        return None
    return df


def regressors(df: pd.DataFrame, pedal_col: str, brake_col: str, v_col: str = "v_mps") -> np.ndarray:
    v = df[v_col].to_numpy()
    pedal = df[pedal_col].to_numpy() if pedal_col in df else np.zeros(len(df))
    brake = df[brake_col].to_numpy() if brake_col in df else np.zeros(len(df))
    # brake -> 0/1
    brake_bin = (brake > 0).astype(float)
    # Avoid NaN in pedal
    pedal = np.nan_to_num(pedal, nan=0.0)
    X = np.column_stack([
        pedal,             # c_thr
        brake_bin,         # c_brk_on
        v,                 # c_v
        v * np.abs(v),     # c_v2 (aero drag)
        np.ones(len(v)),   # c_0
    ])
    return X


def fit_model(dfs: list[pd.DataFrame], pedal_col: str, brake_col: str) -> dict:
    Xs, ys = [], []
    for df in dfs:
        X = regressors(df, pedal_col, brake_col, "v_mps")
        y = df["a_long_mps2"].to_numpy()
        mask = np.isfinite(y) & np.isfinite(X).all(axis=1)
        Xs.append(X[mask])
        ys.append(y[mask])
    X = np.vstack(Xs)
    y = np.concatenate(ys)
    # OLS
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    y_hat = X @ coef
    resid = y - y_hat
    rmse = float(np.sqrt(np.mean(resid ** 2)))
    return {"coef": coef.tolist(), "names": ["thr", "brk_on", "v", "v_abs_v", "const"],
            "rmse_a_train": rmse, "n_train": len(y)}


def predict_a(coef: np.ndarray, pedal: np.ndarray, brake: np.ndarray, v: np.ndarray) -> np.ndarray:
    return (coef[0] * pedal + coef[1] * brake + coef[2] * v
            + coef[3] * v * np.abs(v) + coef[4])


def closed_loop_v(df: pd.DataFrame, coef: np.ndarray, pedal_col: str, brake_col: str) -> np.ndarray:
    t = df["t_s"].to_numpy()
    pedal = np.nan_to_num(df[pedal_col].to_numpy() if pedal_col in df else np.zeros(len(df)))
    brake_raw = df[brake_col].to_numpy() if brake_col in df else np.zeros(len(df))
    brake = (brake_raw > 0).astype(float)
    v = np.empty(len(t))
    v[0] = df["v_mps"].iloc[0]
    for k in range(len(t) - 1):
        dt = t[k + 1] - t[k]
        a = (coef[0] * pedal[k] + coef[1] * brake[k] + coef[2] * v[k]
             + coef[3] * v[k] * abs(v[k]) + coef[4])
        # Clip a to plausible vehicle limits and prevent divergence
        a = float(np.clip(a, -10.0, 6.0))
        v[k + 1] = float(np.clip(v[k] + dt * a, 0.0, 70.0))
    return v


def baseline_v_from_a_meas(df: pd.DataFrame) -> np.ndarray:
    t = df["t_s"].to_numpy()
    a = df["a_long_mps2"].to_numpy()
    v = np.empty(len(t))
    v[0] = df["v_mps"].iloc[0]
    for k in range(len(t) - 1):
        dt = t[k + 1] - t[k]
        v[k + 1] = max(0.0, v[k] + dt * a[k])
    return v


def baseline_v_constant(df: pd.DataFrame) -> np.ndarray:
    """Zero-knowledge baseline: hold initial speed."""
    return np.full(len(df), df["v_mps"].iloc[0])


def regime_mask(df: pd.DataFrame, pedal_col: str, brake_col: str) -> dict:
    a = df["a_long_mps2"].to_numpy()
    v = df["v_mps"].to_numpy()
    pedal = np.nan_to_num(df[pedal_col].to_numpy() if pedal_col in df else np.zeros(len(df)))
    brake_raw = df[brake_col].to_numpy() if brake_col in df else np.zeros(len(df))
    brake = (brake_raw > 0)
    cruise = (np.abs(a) < 0.3) & (v > 5)
    accel = a > 0.5
    brake_r = (a < -0.5) | brake
    coast = (np.abs(a) < 0.5) & (pedal < 1) & (~brake)
    return {"cruise": cruise, "accel": accel, "brake": brake_r, "coast": coast,
            "all": np.ones(len(df), dtype=bool)}


def evaluate(platform: str, train_frac: float = 0.7):
    cfg = PLATFORMS[platform]
    paths = find_segs(platform)
    dfs = []
    for p in paths:
        d = load_seg(p)
        if d is not None:
            dfs.append((p, d))
    rng = np.random.default_rng(7)
    idx = np.arange(len(dfs))
    rng.shuffle(idx)
    n_train = int(train_frac * len(dfs))
    train = [dfs[i][1] for i in idx[:n_train]]
    test = [dfs[i] for i in idx[n_train:]]

    fit = fit_model(train, cfg["pedal"], cfg["brake"])
    coef = np.array(fit["coef"])

    # Evaluate on test set
    per_seg = []
    agg = {k: {"se_model": [], "se_baseline_ameas": [], "se_baseline_const": [], "se_a": []}
           for k in ["all", "cruise", "accel", "brake", "coast"]}
    for path, df in test:
        v_meas = df["v_mps"].to_numpy()
        v_pred = closed_loop_v(df, coef, cfg["pedal"], cfg["brake"])
        v_base = baseline_v_from_a_meas(df)
        v_const = baseline_v_constant(df)
        pedal = np.nan_to_num(df[cfg["pedal"]].to_numpy() if cfg["pedal"] in df else np.zeros(len(df)))
        brake_raw = df[cfg["brake"]].to_numpy() if cfg["brake"] in df else np.zeros(len(df))
        brake = (brake_raw > 0).astype(float)
        a_pred = predict_a(coef, pedal, brake, v_meas)  # one-step using v_meas
        a_meas = df["a_long_mps2"].to_numpy()
        # One-step v prediction using v_meas + dt*a_pred (open-loop, short horizon)
        dt_arr = np.diff(df["t_s"].to_numpy(), prepend=df["t_s"].iloc[0])
        v_onestep = v_meas + dt_arr * a_pred  # one-step ahead
        # Compare v_onestep[:-1] with v_meas[1:]
        v_onestep_err = v_onestep[:-1] - v_meas[1:]
        masks = regime_mask(df, cfg["pedal"], cfg["brake"])
        for k, m in masks.items():
            if m.sum() == 0:
                continue
            agg[k]["se_model"].append(((v_pred - v_meas)[m]) ** 2)
            agg[k]["se_baseline_ameas"].append(((v_base - v_meas)[m]) ** 2)
            agg[k]["se_baseline_const"].append(((v_const - v_meas)[m]) ** 2)
            agg[k]["se_a"].append(((a_pred - a_meas)[m]) ** 2)
        per_seg.append({
            "path": str(path),
            "rmse_v_model_closedloop": float(np.sqrt(np.mean((v_pred - v_meas) ** 2))),
            "rmse_v_onestep": float(np.sqrt(np.mean(v_onestep_err ** 2))),
            "rmse_v_baseline_ameas": float(np.sqrt(np.mean((v_base - v_meas) ** 2))),
            "rmse_v_baseline_const": float(np.sqrt(np.mean((v_const - v_meas) ** 2))),
            "rmse_a_model": float(np.sqrt(np.mean((a_pred - a_meas) ** 2))),
            "duration_s": float(df["t_s"].iloc[-1] - df["t_s"].iloc[0]),
        })

    summary = {"platform": platform, "fit": fit, "n_test_segs": len(test),
               "n_train_segs": n_train, "by_regime": {}}
    for k, v in agg.items():
        if not v["se_model"]:
            continue
        se_m = np.concatenate(v["se_model"])
        se_b = np.concatenate(v["se_baseline_ameas"])
        se_c = np.concatenate(v["se_baseline_const"])
        se_a = np.concatenate(v["se_a"])
        summary["by_regime"][k] = {
            "n": int(se_m.size),
            "rmse_v_model_mps": float(np.sqrt(se_m.mean())),
            "rmse_v_baseline_integrate_ameas_mps": float(np.sqrt(se_b.mean())),
            "rmse_v_baseline_const_v0_mps": float(np.sqrt(se_c.mean())),
            "rmse_a_model_mps2": float(np.sqrt(se_a.mean())),
        }
    return summary, per_seg


def main():
    all_out = {}
    for platform in PLATFORMS:
        print(f"\n=== {platform} ===")
        try:
            summary, per_seg = evaluate(platform)
        except Exception as e:
            print(f"  FAILED: {e}")
            all_out[platform] = {"error": str(e)}
            continue
        all_out[platform] = summary
        # Save per-seg for record
        with open(OUT / f"per_seg_{platform}.json", "w") as f:
            json.dump(per_seg, f, indent=2)
        print(f"  fit coefs (thr, brk_on, v, v|v|, const) = {summary['fit']['coef']}")
        print(f"  RMSE(a_train) = {summary['fit']['rmse_a_train']:.3f} m/s^2  "
              f"n_train={summary['fit']['n_train']}  n_test_segs={summary['n_test_segs']}")
        for k, r in summary["by_regime"].items():
            print(f"    [{k:8s}] n={r['n']:>7d}  "
                  f"v_rmse model={r['rmse_v_model_mps']:6.3f}  "
                  f"const(v0)={r['rmse_v_baseline_const_v0_mps']:6.3f}  "
                  f"int(a_meas)={r['rmse_v_baseline_integrate_ameas_mps']:6.3f}  "
                  f"a_rmse={r['rmse_a_model_mps2']:.3f}")
    with open(OUT / "summary.json", "w") as f:
        json.dump(all_out, f, indent=2)
    print(f"\nWrote {OUT / 'summary.json'}")


if __name__ == "__main__":
    main()
