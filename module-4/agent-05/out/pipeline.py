"""End-to-end pipeline for module-4 v1.01 lateral-fidelity task.

Strategy:
  - V1 baseline (kinematic single-track + understeer + first-order lag + per-seg delta0)
  - Re-fit per-platform coefficients (g, L_eff, K_us, tau) on train split via coordinate descent
  - Per-platform yaw-rate residual learner: linear regression on physically-motivated features
    (v*yr_v1, ay_proxy, steer rate, a_long, sign(yr)*v) to remove the residual structure
    that V1's tuned coefficients can't capture.

Train/dev split: by route folder (first 2 path components) for HYUNDAI and MUSTANG,
by parent route folder for FORD F150. 80/20 by route group hash.
"""
from __future__ import annotations
import hashlib, json, math, sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from load_data import list_segments, load_segment, SIM, PLATFORMS, ROOT  # noqa

import importlib.util
def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
_v1 = _load("v1_baseline", str(ROOT/"code"/"v1_baseline.py"))
predict_v1 = _v1.predict_v1
PLATFORM_PARAMS_V1 = _v1.PLATFORM_PARAMS_V1
_tm = _load("traj_metrics", str(ROOT/"_shared"/"traj_metrics.py"))
cte_rmse_segment = _tm.cte_rmse_segment


def route_key(seg_path: Path, platform: str) -> str:
    """Return a stable route identifier for grouping segments."""
    rel = seg_path.relative_to(SIM / platform).parts
    # rel like ('0b2c0bec9a28eb0f','00000043--caed1d8282','32','sim.csv') for FORD F150
    # or like ('00000001--82c7a5f419','sim.csv')-ish - the first component is a route hash
    return rel[0]


def train_dev_split(segs: list[Path], platform: str, frac_dev: float = 0.25, seed: int = 7) -> tuple[list[Path], list[Path]]:
    routes = {}
    for s in segs:
        r = route_key(s, platform)
        routes.setdefault(r, []).append(s)
    keys = sorted(routes.keys())
    # Hash for deterministic split
    rng = np.random.default_rng(seed)
    idx = np.arange(len(keys))
    rng.shuffle(idx)
    n_dev = max(1, int(len(keys) * frac_dev))
    dev_keys = {keys[i] for i in idx[:n_dev]}
    train, dev = [], []
    for k in keys:
        target = dev if k in dev_keys else train
        for s in routes[k]:
            target.append(s)
    return train, dev


# ----------------------------- predictors -----------------------------

def predict_v1_custom(sim_df: pd.DataFrame, params: dict) -> np.ndarray:
    """Same shape as predict_v1 but with custom params dict."""
    v = sim_df["v_mps"].to_numpy(float)
    delta_road = sim_df["delta_road_rad"].to_numpy(float)
    yr_v0 = sim_df["yaw_rate_pred_rads"].to_numpy(float)
    # per-segment delta0
    if params.get("use_per_segment_delta0", False):
        mask = (np.abs(yr_v0) < 0.03) & (v > 5.0)
        if mask.sum() >= 50:
            d0 = float(np.median(delta_road[mask]))
        else:
            d0 = params.get("delta0_fallback", 0.0)
    else:
        d0 = params.get("delta0", 0.0)
    delta = (delta_road - d0) * params["g"]
    yr_ss = v * delta / (params["L_eff"] + params["K_us"] * v * v)
    t = sim_df["t_s"].to_numpy(float)
    dt = np.diff(t, prepend=t[0])
    alpha = dt / (params["tau"] + dt)
    yr = np.empty_like(yr_ss)
    yr[0] = yr_ss[0]
    for i in range(1, len(yr)):
        yr[i] = yr[i-1] + alpha[i] * (yr_ss[i] - yr[i-1])
    return yr


# ----------------------------- scoring -----------------------------

def eval_yaw_rmse(seg_paths: list[Path], predict_fn) -> tuple[float, int]:
    """Pooled yaw RMSE across segments. predict_fn: (sim_df, platform) -> np.ndarray."""
    ss = 0.0; n = 0
    for sp in seg_paths:
        df = load_segment(sp)
        plat = sp.relative_to(SIM).parts[0]
        yr_pred = predict_fn(df, plat)
        yr_true = df["yaw_rate_meas_rads"].to_numpy(float)
        err = yr_pred - yr_true
        ss += float(np.sum(err*err))
        n += len(err)
    return math.sqrt(ss/n), n


def eval_full(seg_paths: list[Path], predict_fn) -> dict:
    """Pooled yaw RMSE and CTE RMSE across segments."""
    ss_yaw = 0.0; n_yaw = 0
    ss_cte = 0.0; n_bins = 0
    for sp in seg_paths:
        df = load_segment(sp)
        plat = sp.relative_to(SIM).parts[0]
        yr_pred = predict_fn(df, plat)
        yr_true = df["yaw_rate_meas_rads"].to_numpy(float)
        err = yr_pred - yr_true
        ss_yaw += float(np.sum(err*err))
        n_yaw += len(err)
        t = df["t_s"].to_numpy(float)
        v = df["v_mps"].to_numpy(float)
        s_sq, nb, _ = cte_rmse_segment(t, v, yr_true, yr_pred)
        ss_cte += s_sq
        n_bins += nb
    return {
        "yaw_rmse": math.sqrt(ss_yaw/n_yaw) if n_yaw else float("nan"),
        "cte_rmse": math.sqrt(ss_cte/n_bins) if n_bins else float("nan"),
        "n_samples": n_yaw,
        "n_bins": n_bins,
    }


# ------------------ V1 coefficient fit per platform ------------------

def fit_v1_coeffs(train_paths: list[Path], platform: str, base_params: dict) -> dict:
    """Coordinate descent on (g, L_eff, K_us, tau) to minimise yaw RMSE on train."""
    # Pre-load
    train_dfs = [load_segment(p) for p in train_paths]
    def score(params):
        ss = 0.0; n = 0
        for df in train_dfs:
            yr_pred = predict_v1_custom(df, params)
            yr_true = df["yaw_rate_meas_rads"].to_numpy(float)
            err = yr_pred - yr_true
            ss += float(np.sum(err*err))
            n += len(err)
        return math.sqrt(ss/n)
    params = dict(base_params)
    best = score(params)
    print(f"  [{platform}] init train yaw RMSE = {best:.6f}")
    grids = {
        "g":      np.linspace(0.7, 1.05, 8),
        "L_eff":  np.linspace(max(1.5, base_params["L_eff"]*0.7),
                              base_params["L_eff"]*1.3, 9),
        "K_us":   np.linspace(0.0, 0.012, 9),
        "tau":    np.linspace(0.01, 0.20, 11),
    }
    for it in range(3):
        for key, grid in grids.items():
            cur_best = best
            cur_val = params[key]
            for v in grid:
                params[key] = float(v)
                s = score(params)
                if s < cur_best:
                    cur_best = s
                    cur_val = float(v)
            params[key] = cur_val
            best = cur_best
        # narrow the grid around current
        for key in grids:
            cv = params[key]
            span = (grids[key].max() - grids[key].min()) / 4
            grids[key] = np.linspace(max(0.0 if key != "g" else 0.5, cv - span),
                                     cv + span, 9)
    print(f"  [{platform}] fitted train yaw RMSE = {best:.6f}, params={params}")
    return params


# --------- Per-platform residual learner on yaw rate ---------

def build_features(df: pd.DataFrame, yr_v1: np.ndarray) -> np.ndarray:
    v = df["v_mps"].to_numpy(float)
    delta = df["delta_road_rad"].to_numpy(float)
    a_long = df["a_long_mps2"].to_numpy(float)
    yr_v0 = df["yaw_rate_pred_rads"].to_numpy(float)
    # steer rate
    t = df["t_s"].to_numpy(float)
    dt = np.diff(t, prepend=t[0])
    dt = np.where(dt > 0, dt, 1e-3)
    d_delta = np.gradient(delta, t) if len(t) > 1 else np.zeros_like(delta)
    # lateral accel proxy
    ay = v * yr_v1
    # |yr| nonlinearity
    yrv1_abs = np.abs(yr_v1)
    sgn_yr = np.sign(yr_v1)
    feats = np.column_stack([
        np.ones_like(v),
        yr_v1,               # scale correction
        ay,                  # ay-coupled bias
        v,                   # speed-coupled bias
        a_long,              # accel-coupled
        a_long * yr_v1,      # load-transfer term
        d_delta,             # steer-rate (lag correction)
        yr_v1 * yr_v1 * sgn_yr,  # tyre saturation cubic
        delta * v,           # combined steer-speed
        yrv1_abs * v,        # nonlinear understeer
    ])
    return feats


def fit_residual_learner(train_paths: list[Path], v1_params: dict, platform: str,
                         ridge_lambda: float = 1e-2) -> np.ndarray:
    """Ridge regression on yaw-rate residual."""
    X_list = []; y_list = []
    for sp in train_paths:
        df = load_segment(sp)
        yr_v1 = predict_v1_custom(df, v1_params)
        feats = build_features(df, yr_v1)
        yr_true = df["yaw_rate_meas_rads"].to_numpy(float)
        resid = yr_true - yr_v1
        X_list.append(feats); y_list.append(resid)
    X = np.vstack(X_list); y = np.concatenate(y_list)
    # Standardize columns except the intercept
    mu = X.mean(axis=0); sd = X.std(axis=0); sd[sd < 1e-12] = 1.0
    mu[0] = 0.0; sd[0] = 1.0
    Xs = (X - mu) / sd
    n, k = Xs.shape
    A = Xs.T @ Xs + ridge_lambda * np.eye(k)
    A[0, 0] -= ridge_lambda  # leave intercept un-penalised
    b = Xs.T @ y
    w = np.linalg.solve(A, b)
    # store (mu, sd, w) collapsed into a single coeff vector to apply in standardized form
    return mu, sd, w


def apply_residual(df: pd.DataFrame, yr_v1: np.ndarray, mu, sd, w) -> np.ndarray:
    feats = build_features(df, yr_v1)
    Xs = (feats - mu) / sd
    delta_yr = Xs @ w
    return yr_v1 + delta_yr


# ----------------------------- main -----------------------------

def main():
    base = {p: dict(PLATFORM_PARAMS_V1[p]) for p in PLATFORMS}
    out_dir = ROOT / "out"
    coeffs = {}
    splits = {}
    for plat in PLATFORMS:
        segs = list_segments(plat)
        train, dev = train_dev_split(segs, plat, frac_dev=0.25, seed=7)
        splits[plat] = {"train": [str(p) for p in train], "dev": [str(p) for p in dev]}
        print(f"\n=== {plat}: {len(train)} train / {len(dev)} dev ===")

        # V0 (pass-through pred col) score on dev
        v0_pred = lambda df_, _p: df_["yaw_rate_pred_rads"].to_numpy(float)
        s_v0 = eval_full(dev, v0_pred)
        print(f"  V0 dev: yaw={s_v0['yaw_rmse']:.5f} cte={s_v0['cte_rmse']:.3f}")

        # V1 (canonical)
        v1_pred = lambda df_, p_: predict_v1(df_, p_)["yaw_rate_pred_rads"].to_numpy(float)
        s_v1 = eval_full(dev, v1_pred)
        print(f"  V1 dev: yaw={s_v1['yaw_rmse']:.5f} cte={s_v1['cte_rmse']:.3f}")

        # Fit V1 coeffs
        fit_params_try = fit_v1_coeffs(train, plat, base[plat])
        def v1fit_pred_plat(df_, p_, fp=fit_params_try, pl=plat):
            if p_ != pl:
                return predict_v1(df_, p_)["yaw_rate_pred_rads"].to_numpy(float)
            return predict_v1_custom(df_, fp)
        s_v1f_try = eval_full(dev, v1fit_pred_plat)
        print(f"  V1+fit(try) dev: yaw={s_v1f_try['yaw_rmse']:.5f} cte={s_v1f_try['cte_rmse']:.3f}")
        # Pick whichever beats V1 on dev
        if s_v1f_try["yaw_rmse"] < s_v1["yaw_rmse"]:
            fit_params, s_v1f = fit_params_try, s_v1f_try
            print(f"  -> using fitted params")
        else:
            fit_params, s_v1f = base[plat], s_v1
            print(f"  -> keeping V1 baseline params")

        # Residual learner — sweep ridge, pick the one that minimises dev yaw RMSE
        best = (s_v1f["yaw_rmse"], None, None, None, "v1_fit")
        for rl in [1e-4, 1e-3, 1e-2, 1e-1, 1.0, 10.0, 100.0]:
            mu_, sd_, w_ = fit_residual_learner(train, fit_params, plat, ridge_lambda=rl)
            def pf(df_, p_, fp=fit_params, mu=mu_, sd=sd_, w=w_, pl=plat):
                if p_ != pl:
                    return predict_v1(df_, p_)["yaw_rate_pred_rads"].to_numpy(float)
                yr_v1 = predict_v1_custom(df_, fp)
                return apply_residual(df_, yr_v1, mu, sd, w)
            s_ = eval_full(dev, pf)
            print(f"    resid ridge={rl:g}: yaw={s_['yaw_rmse']:.5f} cte={s_['cte_rmse']:.3f}")
            if s_["yaw_rmse"] < best[0]:
                best = (s_["yaw_rmse"], mu_, sd_, w_, rl)
        chose = best[4]
        mu, sd, w = best[1], best[2], best[3]
        use_resid = (mu is not None)
        print(f"  chose ridge={chose}, use_resid={use_resid}")
        if use_resid:
            def v1res_pred_plat(df_, p_, fp=fit_params, mu=mu, sd=sd, w=w, pl=plat):
                if p_ != pl:
                    return predict_v1(df_, p_)["yaw_rate_pred_rads"].to_numpy(float)
                yr_v1 = predict_v1_custom(df_, fp)
                return apply_residual(df_, yr_v1, mu, sd, w)
            s_v1r = eval_full(dev, v1res_pred_plat)
            print(f"  V1+fit+resid dev: yaw={s_v1r['yaw_rmse']:.5f} cte={s_v1r['cte_rmse']:.3f}")
        else:
            s_v1r = s_v1f

        coeffs[plat] = {
            "v1_params": fit_params,
            "use_resid": bool(use_resid),
            "resid_mu": mu.tolist() if mu is not None else None,
            "resid_sd": sd.tolist() if sd is not None else None,
            "resid_w": w.tolist() if w is not None else None,
            "resid_ridge": chose,
            "dev_scores": {
                "v0": s_v0, "v1": s_v1, "v1_fit": s_v1f, "v1_fit_resid": s_v1r,
            }
        }

    out = out_dir / "coeffs.json"
    out.write_text(json.dumps(coeffs, indent=2, default=float))
    (out_dir / "splits.json").write_text(json.dumps(splits, indent=2))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
