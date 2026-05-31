"""Fit per-platform understeer correction: yr = yr_pred / (1 + K * v^2) + bias.

Compare against pure linear (a, b) and against pure scalar multiplier.
Use train/test split: route-based.
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import minimize

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-06")
SEG_ROOT = ROOT / "data" / "sim" / "segments"
sys.path.insert(0, str(ROOT / "_shared"))
from traj_metrics import cte_diagnostics_segment  # noqa: E402

PLATFORMS = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]


def load_segs(platform: str, rng_seed: int = 0, n_train: int = 120, n_test: int = 30):
    paths = sorted((SEG_ROOT / platform).glob("**/sim.csv"))
    # Group by route
    routes = {}
    for p in paths:
        r = p.resolve().parents[1].name
        routes.setdefault(r, []).append(p)
    route_keys = sorted(routes.keys())
    rng = np.random.default_rng(rng_seed)
    rng.shuffle(route_keys)
    n_routes = len(route_keys)
    # ~80/20 split by route
    cut = int(0.8 * n_routes)
    train_routes = route_keys[:cut]
    test_routes = route_keys[cut:]
    train_paths = [p for r in train_routes for p in routes[r]]
    test_paths  = [p for r in test_routes for p in routes[r]]
    # Subsample for fitting
    rng.shuffle(train_paths)
    rng.shuffle(test_paths)
    train_paths = train_paths[:n_train]
    test_paths  = test_paths[:n_test]
    return train_paths, test_paths


def gather_samples(paths):
    """Return arrays for sample-pooled yaw fitting."""
    dfs = []
    for p in paths:
        df = pd.read_csv(p)
        df = df[df["v_mps"] > 2.0]
        if len(df) < 10:
            continue
        dfs.append(df[["v_mps", "delta_road_rad", "yaw_rate_meas_rads", "yaw_rate_pred_rads"]])
    if not dfs:
        return None
    return pd.concat(dfs, ignore_index=True)


def yaw_rmse(pred, truth):
    return float(np.sqrt(np.mean((pred - truth) ** 2)))


def fit_understeer(df, model="A"):
    """Fit understeer coefficient K (and optional bias b).

    model A: yr = yr_pred / (1 + K*v^2)
    model B: yr = yr_pred / (1 + K*v^2) + b
    model C: yr = a * yr_pred / (1 + K*v^2) + b   (gain + understeer + bias)
    """
    v = df["v_mps"].to_numpy()
    p = df["yaw_rate_pred_rads"].to_numpy()
    t = df["yaw_rate_meas_rads"].to_numpy()

    if model == "A":
        def loss(x):
            K, = x
            denom = 1.0 + K * v * v
            yr = p / denom
            return float(np.mean((yr - t) ** 2))
        res = minimize(loss, [0.001], method="Nelder-Mead")
        return {"K": float(res.x[0])}
    if model == "B":
        def loss(x):
            K, b = x
            denom = 1.0 + K * v * v
            yr = p / denom + b
            return float(np.mean((yr - t) ** 2))
        res = minimize(loss, [0.001, 0.0], method="Nelder-Mead")
        return {"K": float(res.x[0]), "b": float(res.x[1])}
    if model == "C":
        def loss(x):
            a, K, b = x
            denom = 1.0 + K * v * v
            yr = a * p / denom + b
            return float(np.mean((yr - t) ** 2))
        res = minimize(loss, [1.0, 0.001, 0.0], method="Nelder-Mead")
        return {"a": float(res.x[0]), "K": float(res.x[1]), "b": float(res.x[2])}
    raise ValueError(model)


def apply_model(df, coef, model):
    v = df["v_mps"].to_numpy()
    p = df["yaw_rate_pred_rads"].to_numpy()
    denom = 1.0 + coef["K"] * v * v
    if model == "A":
        return p / denom
    if model == "B":
        return p / denom + coef["b"]
    if model == "C":
        return coef["a"] * p / denom + coef["b"]
    raise ValueError(model)


def cte_for_paths(paths, coef, model):
    sum_sq = 0.0
    n_bins = 0
    sum_sq_v0 = 0.0
    n_bins_v0 = 0
    for p in paths:
        df = pd.read_csv(p)
        if "yaw_rate_meas_rads" not in df.columns:
            continue
        t = df["t_s"].to_numpy(float)
        v = df["v_mps"].to_numpy(float)
        yr_t = df["yaw_rate_meas_rads"].to_numpy(float)
        yr_v0 = df["yaw_rate_pred_rads"].to_numpy(float)
        # Apply correction
        denom = 1.0 + coef["K"] * v * v
        if model == "A":
            yr_p = yr_v0 / denom
        elif model == "B":
            yr_p = yr_v0 / denom + coef["b"]
        elif model == "C":
            yr_p = coef["a"] * yr_v0 / denom + coef["b"]
        d = cte_diagnostics_segment(t, v, yr_t, yr_p)
        sum_sq += d["sum_sq_m2"]; n_bins += d["n_bins"]
        d0 = cte_diagnostics_segment(t, v, yr_t, yr_v0)
        sum_sq_v0 += d0["sum_sq_m2"]; n_bins_v0 += d0["n_bins"]
    cte = float(np.sqrt(sum_sq / n_bins)) if n_bins > 0 else float("nan")
    cte_v0 = float(np.sqrt(sum_sq_v0 / n_bins_v0)) if n_bins_v0 > 0 else float("nan")
    return cte, cte_v0


def main():
    fits = {}
    for plat in PLATFORMS:
        print(f"\n===== {plat} =====")
        train_paths, test_paths = load_segs(plat, n_train=140, n_test=40)
        train_df = gather_samples(train_paths)
        test_df  = gather_samples(test_paths)
        print(f" train samples n={len(train_df)}, test samples n={len(test_df)}")
        # V0 baseline RMSE on test
        v0_train = yaw_rmse(train_df["yaw_rate_pred_rads"].to_numpy(), train_df["yaw_rate_meas_rads"].to_numpy())
        v0_test  = yaw_rmse(test_df["yaw_rate_pred_rads"].to_numpy(),  test_df["yaw_rate_meas_rads"].to_numpy())
        print(f" V0 yaw RMSE: train={v0_train:.6f}, test={v0_test:.6f}")

        results = {}
        for m in ("A", "B", "C"):
            coef = fit_understeer(train_df, model=m)
            yr_train = apply_model(train_df, coef, m)
            yr_test  = apply_model(test_df,  coef, m)
            tr_r = yaw_rmse(yr_train, train_df["yaw_rate_meas_rads"].to_numpy())
            te_r = yaw_rmse(yr_test,  test_df["yaw_rate_meas_rads"].to_numpy())
            print(f" Model {m} coef={coef}, RMSE train={tr_r:.6f}, test={te_r:.6f}")
            results[m] = coef

        # Pick best by test RMSE on full sample-pooled basis: model C usually
        # Compute CTE on test for model C
        coef_c = results["C"]
        cte_test, cte_v0 = cte_for_paths(test_paths, coef_c, "C")
        print(f" Model C CTE test: v0={cte_v0:.2f}m -> {cte_test:.2f}m")
        # Also model A
        coef_a = results["A"]
        cte_a, _ = cte_for_paths(test_paths, coef_a, "A")
        print(f" Model A CTE test: -> {cte_a:.2f}m")
        # Also model B
        coef_b = results["B"]
        cte_b, _ = cte_for_paths(test_paths, coef_b, "B")
        print(f" Model B CTE test: -> {cte_b:.2f}m")
        fits[plat] = results
    return fits


if __name__ == "__main__":
    fits = main()
    import json
    out = {}
    for plat, models in fits.items():
        out[plat] = {m: {k: float(v) for k, v in c.items()} for m, c in models.items()}
    (ROOT / "out" / "understeer_fits.json").write_text(json.dumps(out, indent=2))
    print("\nSaved understeer_fits.json")
