"""Build & validate a longitudinal model that predicts v_mps from commanded inputs.

Baseline (the crutch): v_pred(t) = v_meas(t)      — perfect by construction.
What we replace: a model that predicts a_long from (accel_pedal_pct, brake_pedal_state, v),
then integrates v.

Two simpler reference baselines we compare against:
  - "hold-v": v_pred(t) = v_meas(0)               (no model — constant)
  - "kinematic-known-a": use measured a_long as input (open-loop integration of a)
Our model:
  - "long-model": a_pred = f(pedal, brake, v) with a tiny calibrated parametric form.

Validation:
  - Open-loop one-step: predict a_long(t) given measured (pedal, brake, v(t)),
    compare to measured a_long(t).
  - Closed-loop integration over fixed horizons (5 s, full-segment), starting from
    v_meas(0); inputs fed are *commanded* (accel_pedal_pct, brake_pedal_state) plus
    the model's own internal v state. Compare integrated v to v_meas.

Regimes from measured a_long & pedal state.
"""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from collections import defaultdict

import numpy as np

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-09")
SIM_ROOT = ROOT / "data" / "sim" / "segments"
OUT_DIR = ROOT / "out"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PLATFORMS = ["TESLA_MODEL_3", "FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]

# Physical constants / per-platform defaults (rough, openpilot-ish where possible)
PLATFORM_MASS = {
    "TESLA_MODEL_3": 2035.0,
    "FORD_MUSTANG_MACH_E_MK1": 2336.0,
    "FORD_F_150_LIGHTNING_MK1": 3084.0,
}


def list_sim_csvs(platform: str) -> list[Path]:
    root = SIM_ROOT / platform
    if not root.exists():
        return []
    return sorted(root.rglob("sim.csv"))


def load_csv(path: Path):
    """Load relevant columns from a sim.csv as a dict of np arrays."""
    cols = defaultdict(list)
    with open(path) as f:
        r = csv.DictReader(f)
        for row in r:
            for k, v in row.items():
                cols[k].append(v)
    out = {}
    for k, v in cols.items():
        try:
            out[k] = np.array(v, dtype=float)
        except ValueError:
            out[k] = np.array(v)
    return out


# -----------------------------------------------------------------------------
# Model: parametric a_long = f(pedal, brake, v)
# -----------------------------------------------------------------------------
#
# We use a tiny physics-flavored parametric form. Tractive accel comes from accel
# pedal (effective drive torque ~ pedal * peak, decreasing slightly with speed
# due to power-cap regime). Brake deceleration is a thresholded function of the
# brake pedal state. Drag terms (rolling + aero) oppose motion.
#
#   a_pred = a_drive(pedal, v) + a_brake(brake_state, v) - a_drag(v) - a_regen(pedal, v)
#
# where:
#   a_drive  = k_p * pedal_frac * sat(P_max / (m * max(v, v0)))  (power-limited above v0)
#              -> simpler: a_drive = (k1 - k2 * v) * pedal_frac  with positive (k1, k2)
#   a_brake  = -b0 - b1 * v  if brake_state > 1 else 0   (state encodes pressed)
#   a_drag   = c0 + c1 * v + c2 * v^2     (rolling + linear damping + aero)
#   a_regen  = r0 * (1 - pedal_frac) * v   (lift-off light regen, EV-typical)
#
# We fit parameters by linear least-squares on a training fold of segments,
# then evaluate on held-out segments.


def get_brake(d: dict, v: np.ndarray) -> np.ndarray:
    """Unified brake-pressed indicator across platforms."""
    if "brake_pressed" in d:
        return (d["brake_pressed"] > 0.5).astype(float)
    if "brake_pedal_state" in d:
        # Tesla rlog enum: typical values 1=released, 2=light, 3+=pressed.
        # Empirically in our CSVs this is constant 2 (no useful info), so we
        # return zeros and let the regression rely on (pedal, lift-off) instead.
        st = d["brake_pedal_state"]
        return (st > 2.5).astype(float)
    return np.zeros_like(v)


def build_features(d: dict) -> np.ndarray:
    """Return feature matrix X (N, K) for the linear a_long regressor."""
    v = d["v_mps"]
    pedal = d["accel_pedal_pct"] / 100.0
    brake_pressed = get_brake(d, v)
    liftoff = (pedal < 0.02).astype(float)   # foot off the throttle
    # Columns: [1, v, v^2, pedal, pedal*v, brake, brake*v, liftoff*v, liftoff]
    return np.column_stack([
        np.ones_like(v),
        v,
        v * v,
        pedal,
        pedal * v,
        brake_pressed,
        brake_pressed * v,
        liftoff * v,
        liftoff,
    ])


FEATURE_NAMES = ["1", "v", "v^2", "pedal", "pedal*v",
                 "brake", "brake*v", "lift*v", "lift"]


def fit_long_model(train_csvs: list[Path], cap_rows_per_file: int = 1500):
    Xs, ys = [], []
    for p in train_csvs:
        d = load_csv(p)
        if "a_long_mps2" not in d:
            continue
        X = build_features(d)
        y = d["a_long_mps2"]
        # Drop NaN/Inf rows and physical outliers (some F-150 segments have a-glitches)
        v_arr = d["v_mps"]
        mask = (
            np.isfinite(X).all(axis=1)
            & np.isfinite(y)
            & np.isfinite(v_arr)
            & (v_arr >= 0) & (v_arr < 80)            # < 290 km/h
            & (np.abs(y) < 12.0)                      # |a| < 12 m/s^2
        )
        X, y = X[mask], y[mask]
        if X.shape[0] > cap_rows_per_file:
            idx = np.linspace(0, X.shape[0] - 1, cap_rows_per_file).astype(int)
            X, y = X[idx], y[idx]
        Xs.append(X)
        ys.append(y)
    X = np.vstack(Xs)
    y = np.concatenate(ys)
    # Ridge-regularised least squares
    lam = 1e-3
    A = X.T @ X + lam * np.eye(X.shape[1])
    b = X.T @ y
    theta = np.linalg.solve(A, b)
    return theta


def predict_a(theta: np.ndarray, v: float, pedal_frac: float, brake_pressed: float):
    liftoff = 1.0 if pedal_frac < 0.02 else 0.0
    feats = np.array([
        1.0, v, v * v, pedal_frac, pedal_frac * v,
        brake_pressed, brake_pressed * v, liftoff * v, liftoff,
    ])
    return float(feats @ theta)


# -----------------------------------------------------------------------------
# Evaluation
# -----------------------------------------------------------------------------

def regime_mask(d: dict):
    """Categorise each sample into regime."""
    a = d["a_long_mps2"]
    v = d["v_mps"]
    brake = get_brake(d, v) > 0.5
    pedal = d["accel_pedal_pct"]
    accel = (a > 0.5) & (pedal > 5)
    brake_r = (a < -0.5) & brake
    coast = (np.abs(a) < 0.3) & (pedal < 2) & ~brake
    cruise = (np.abs(a) < 0.3) & (pedal >= 2) & ~brake
    other = ~(accel | brake_r | coast | cruise)
    return {
        "accel": accel,
        "brake": brake_r,
        "coast": coast,
        "cruise": cruise,
        "other": other,
    }


def eval_one_step(theta, csvs):
    """Open-loop one-step: predict a_long(t) given measured (pedal, brake, v).
    Returns RMSE on a_long, and on the implied v at next step using dt."""
    all_a_err = []
    all_v_err_dt = []  # v error at t+1 if you Euler-step from measured v with predicted a
    regime_a_err = defaultdict(list)
    for p in csvs:
        d = load_csv(p)
        if "a_long_mps2" not in d:
            continue
        # filter physical outliers from test as well (same filter we trained under)
        v = d["v_mps"]; a = d["a_long_mps2"]
        keep = (np.isfinite(v) & np.isfinite(a)
                & (v >= 0) & (v < 80) & (np.abs(a) < 12.0))
        if not keep.any():
            continue
        d = {k: (vv[keep] if isinstance(vv, np.ndarray) and vv.ndim == 1 and vv.shape[0] == keep.shape[0] else vv) for k, vv in d.items()}
        X = build_features(d)
        a_meas = d["a_long_mps2"]
        a_pred = X @ theta
        err = a_pred - a_meas
        all_a_err.append(err)
        # v step error
        t = d["t_s"]
        dt = float(np.median(np.diff(t)))
        v_err = err * dt
        all_v_err_dt.append(v_err)
        rg = regime_mask(d)
        for name, mask in rg.items():
            if mask.any():
                regime_a_err[name].append(err[mask])
    aerr = np.concatenate(all_a_err)
    rmse_a = float(np.sqrt(np.mean(aerr ** 2)))
    mae_a = float(np.mean(np.abs(aerr)))
    regime_stats = {}
    for k, errs in regime_a_err.items():
        e = np.concatenate(errs)
        regime_stats[k] = {
            "n": int(e.size),
            "rmse_a": float(np.sqrt(np.mean(e ** 2))),
            "mae_a": float(np.mean(np.abs(e))),
            "bias_a": float(np.mean(e)),
        }
    return {
        "rmse_a_mps2": rmse_a,
        "mae_a_mps2": mae_a,
        "regimes": regime_stats,
    }


def integrate_closed_loop(theta, d, a_max=8.0, a_min=-10.0, v_max=70.0):
    """Integrate v(t) using the model from v(0), with measured (pedal, brake) as commanded inputs."""
    t = d["t_s"]
    v_meas = d["v_mps"]
    pedal = d["accel_pedal_pct"] / 100.0
    brake_pressed = get_brake(d, v_meas)
    N = len(t)
    v_pred = np.zeros(N)
    v_pred[0] = max(0.0, min(v_max, float(v_meas[0])))
    for k in range(N - 1):
        dt = float(t[k + 1] - t[k])
        v = v_pred[k]
        a = predict_a(theta, v, pedal[k], brake_pressed[k])
        # actuator saturation
        a = max(a_min, min(a_max, a))
        v_pred[k + 1] = max(0.0, min(v_max, v_pred[k] + a * dt))
    return v_pred


def eval_closed_loop(theta, csvs, horizons_s=(5.0, 10.0, 30.0)):
    """Closed-loop integration RMSE over horizons + full-segment."""
    horizon_errs = {h: [] for h in horizons_s}
    full_errs = []
    hold_full_errs = []
    naive_a_full_errs = []
    for p in csvs:
        d = load_csv(p)
        if "v_mps" not in d or "a_long_mps2" not in d:
            continue
        v = d["v_mps"]; a = d["a_long_mps2"]
        keep = (np.isfinite(v) & np.isfinite(a)
                & (v >= 0) & (v < 80) & (np.abs(a) < 12.0))
        if keep.sum() < 50:
            continue
        d = {k: (vv[keep] if isinstance(vv, np.ndarray) and vv.ndim == 1 and vv.shape[0] == keep.shape[0] else vv) for k, vv in d.items()}
        t = d["t_s"]
        v_meas = d["v_mps"]
        dt = float(np.median(np.diff(t)))
        # model integration
        v_pred = integrate_closed_loop(theta, d)
        err = v_pred - v_meas
        full_errs.append(err)
        # hold baseline
        hold = np.full_like(v_meas, v_meas[0])
        hold_full_errs.append(hold - v_meas)
        # naive-a baseline: integrate measured a from v(0)
        v_naive = np.zeros_like(v_meas)
        v_naive[0] = v_meas[0]
        a_meas = d["a_long_mps2"]
        for k in range(len(t) - 1):
            v_naive[k + 1] = max(0.0, v_naive[k] + a_meas[k] * (t[k + 1] - t[k]))
        naive_a_full_errs.append(v_naive - v_meas)
        for h in horizons_s:
            steps = int(round(h / dt))
            if steps + 1 < len(t):
                horizon_errs[h].append(err[:steps + 1])

    def rmse(es):
        e = np.concatenate(es)
        return float(np.sqrt(np.mean(e ** 2)))

    return {
        "model_rmse_v_mps_full": rmse(full_errs),
        "hold_baseline_rmse_v_mps_full": rmse(hold_full_errs),
        "integrate_measured_a_rmse_v_mps_full": rmse(naive_a_full_errs),
        "model_rmse_v_mps_by_horizon": {
            f"{h:.0f}s": rmse(horizon_errs[h]) if horizon_errs[h] else None
            for h in horizons_s
        },
    }


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def split(csvs, train_frac=0.7, max_total=120, seed=0):
    rng = np.random.default_rng(seed)
    if len(csvs) > max_total:
        idx = rng.choice(len(csvs), size=max_total, replace=False)
        csvs = [csvs[i] for i in sorted(idx)]
    rng.shuffle(csvs)
    n_train = int(len(csvs) * train_frac)
    return csvs[:n_train], csvs[n_train:]


def main():
    results = {}
    for platform in PLATFORMS:
        csvs = list_sim_csvs(platform)
        if len(csvs) < 4:
            print(f"[{platform}] not enough segments ({len(csvs)}), skipping")
            continue
        train, test = split(csvs, max_total=80)
        print(f"[{platform}] {len(train)} train / {len(test)} test segments")
        theta = fit_long_model(train)
        print(f"  theta = {dict(zip(FEATURE_NAMES, theta.round(4).tolist()))}")
        one_step = eval_one_step(theta, test)
        closed = eval_closed_loop(theta, test)
        results[platform] = {
            "n_train_segments": len(train),
            "n_test_segments": len(test),
            "theta": {n: float(v) for n, v in zip(FEATURE_NAMES, theta)},
            "open_loop_one_step": one_step,
            "closed_loop": closed,
        }
        print(f"  open-loop one-step RMSE a: {one_step['rmse_a_mps2']:.4f} m/s^2")
        print(f"  closed-loop full-segment RMSE v: {closed['model_rmse_v_mps_full']:.4f} m/s")
        print(f"   hold baseline RMSE v: {closed['hold_baseline_rmse_v_mps_full']:.4f} m/s")
        print(f"   integrate measured-a (oracle-a) RMSE v: {closed['integrate_measured_a_rmse_v_mps_full']:.4f} m/s")
        for k, v in one_step["regimes"].items():
            print(f"    regime {k:8s}: n={v['n']:6d}  rmse_a={v['rmse_a']:.3f}  bias={v['bias_a']:+.3f}")

    out = OUT_DIR / "long_model_results.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
