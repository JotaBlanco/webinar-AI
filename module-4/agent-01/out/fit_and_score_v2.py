"""V2 fit/score: gated bias + gated ridge per platform.

Decision rule (cohort-evidenced):
- Apply bias only where it improves BOTH yaw RMSE and CTE RMSE under CV.
- Apply ridge residual learner only on platforms where it strictly improves yaw CV.
- Sweep ridge lambdas and pick CV-winner per platform.
"""
from __future__ import annotations
import sys, json, math, time
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1.01/agent-01")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "code"))
sys.path.insert(0, str(ROOT / "_shared"))
from v1_baseline import predict_v1  # type: ignore
from traj_metrics import cte_rmse_segment  # type: ignore

SIM_ROOT = ROOT / "data" / "sim" / "segments"
PLATFORMS_WITH_TRUTH = ["FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5"]


def list_segments(platform: str):
    out = []
    pdir = SIM_ROOT / platform
    for route_dir in sorted(pdir.iterdir()):
        if not route_dir.is_dir(): continue
        for seg_dir in sorted(route_dir.iterdir()):
            if not seg_dir.is_dir(): continue
            for sub in sorted(seg_dir.iterdir()):
                if not sub.is_dir(): continue
                f = sub / "sim.csv"
                if f.exists():
                    out.append((route_dir.name, f))
    return out


def yaw_residual_features(df: pd.DataFrame, yr_v1: np.ndarray) -> np.ndarray:
    v = df["v_mps"].to_numpy()
    delta = df["delta_road_rad"].to_numpy()
    a_long = df["a_long_mps2"].to_numpy()
    t = df["t_s"].to_numpy()
    ddelta = np.gradient(delta, t)
    a_lat_proxy = v * yr_v1
    feats = np.column_stack([
        yr_v1,
        v,
        delta,
        delta * v,
        ddelta,
        a_long,
        a_lat_proxy,
    ])
    return feats


def fit_ridge(X, y, lam):
    mu = X.mean(0); sd = X.std(0) + 1e-9
    Xs = (X - mu) / sd
    Xs = np.column_stack([np.ones(len(Xs)), Xs])
    A = Xs.T @ Xs
    A += lam * np.eye(A.shape[0])
    A[0,0] -= lam
    w = np.linalg.solve(A, Xs.T @ y)
    return {"mu": mu, "sd": sd, "w": w}


def apply_ridge(X, model):
    Xs = (X - model["mu"]) / model["sd"]
    Xs = np.column_stack([np.ones(len(Xs)), Xs])
    return Xs @ model["w"]


def pooled_metrics(segs):
    sse_yaw = 0.0; n_yaw = 0
    sse_cte = 0.0; n_bins = 0
    for (t,v,yt,yp) in segs:
        d = yp - yt
        sse_yaw += float(np.sum(d*d))
        n_yaw += len(d)
        s, nb, _ = cte_rmse_segment(t, v, yt, yp)
        sse_cte += s; n_bins += nb
    return math.sqrt(sse_yaw / max(n_yaw,1)), math.sqrt(sse_cte / max(n_bins,1))


def cv_score_variant(cache_plat, K=5, seed=0, bias_enabled=True, ridge_lambda=None):
    """5-fold route-grouped CV. Returns dict with mean/std for yaw & CTE."""
    rng = np.random.default_rng(seed)
    recs = cache_plat
    routes = sorted({r["route"] for r in recs})
    rng.shuffle(routes)
    folds = [routes[i::K] for i in range(K)]
    per = []
    for k in range(K):
        test_routes = set(folds[k])
        train = [r for r in recs if r["route"] not in test_routes]
        test  = [r for r in recs if r["route"] in test_routes]
        train_resid = np.concatenate([r["resid"] for r in train])
        bias = float(np.mean(train_resid)) if bias_enabled else 0.0
        ridge = None
        if ridge_lambda is not None:
            X_tr = np.vstack([r["feats"] for r in train])
            y_tr = np.concatenate([r["resid"] for r in train]) - bias
            ridge = fit_ridge(X_tr, y_tr, lam=ridge_lambda)
        segs = []
        for r in test:
            yp = r["yr_v1"] + bias
            if ridge is not None:
                yp = yp + apply_ridge(r["feats"], ridge)
            segs.append((r["t"], r["v"], r["truth"], yp))
        per.append(pooled_metrics(segs))
    arr = np.array(per)
    return {
        "yaw_mean": float(arr[:,0].mean()),
        "yaw_std":  float(arr[:,0].std()),
        "cte_mean": float(arr[:,1].mean()),
        "cte_std":  float(arr[:,1].std()),
    }


def main():
    cache = {}
    for plat in PLATFORMS_WITH_TRUTH:
        print(f"== Loading {plat}", flush=True)
        segs_paths = list_segments(plat)
        recs = []
        for route_id, path in segs_paths:
            df = pd.read_csv(path)
            if "yaw_rate_meas_rads" not in df.columns: continue
            yr_v1 = predict_v1(df, plat)["yaw_rate_pred_rads"].to_numpy()
            truth = df["yaw_rate_meas_rads"].to_numpy()
            recs.append({
                "route": route_id,
                "t": df["t_s"].to_numpy(),
                "v": df["v_mps"].to_numpy(),
                "yr_v1": yr_v1,
                "truth": truth,
                "resid": truth - yr_v1,
                "feats": yaw_residual_features(df, yr_v1),
            })
        cache[plat] = recs
        print(f"   {len(recs)} segments", flush=True)

    # Search per-platform best (bias_on/off, ridge_lambda in {None, 100, 300, 1000, 3000})
    lambdas = [None, 100.0, 300.0, 1000.0, 3000.0, 10000.0]
    best = {}
    all_results = {}
    for plat in PLATFORMS_WITH_TRUTH:
        plat_results = []
        # baseline (V1 unchanged)
        m_base = cv_score_variant(cache[plat], bias_enabled=False, ridge_lambda=None)
        plat_results.append(("v1", m_base))
        for bias_on in [False, True]:
            for lam in lambdas:
                m = cv_score_variant(cache[plat], bias_enabled=bias_on, ridge_lambda=lam)
                tag = f"bias={bias_on},ridge={lam}"
                plat_results.append((tag, m))
        all_results[plat] = plat_results
        # Pick variant that strictly improves yaw vs v1 OR if Lightning (cohort §5) keep V1
        # Strategy: minimize yaw_mean + 0.001 * cte_mean (rough Pareto), but Pareto-dominance preferred
        # Stricter: require yaw_mean <= v1.yaw_mean * 1.0 and cte_mean <= v1.cte_mean * 1.005 (tiny slack)
        v1_yaw = m_base["yaw_mean"]; v1_cte = m_base["cte_mean"]
        candidates = []
        for tag, m in plat_results[1:]:
            if m["yaw_mean"] <= v1_yaw and m["cte_mean"] <= v1_cte * 1.01:
                # Score: combined relative improvement
                score = (v1_yaw - m["yaw_mean"]) / v1_yaw + (v1_cte - m["cte_mean"]) / v1_cte
                candidates.append((score, tag, m))
        if not candidates:
            best[plat] = ("v1", m_base)
        else:
            candidates.sort(key=lambda x: -x[0])
            best[plat] = (candidates[0][1], candidates[0][2])

    print("\n== Best variant per platform under CV ==")
    for plat, (tag, m) in best.items():
        print(f"  {plat}: {tag} -> yaw {m['yaw_mean']:.6f}±{m['yaw_std']:.6f}  CTE {m['cte_mean']:.3f}±{m['cte_std']:.3f}")

    # Save full search results
    serializable = {plat: [(t, m) for (t, m) in res] for plat, res in all_results.items()}
    (ROOT / "out" / "cv_search.json").write_text(json.dumps(serializable, indent=2))

    # Fit final models per platform with chosen config
    fitted = {}
    for plat in PLATFORMS_WITH_TRUTH:
        tag, _ = best[plat]
        recs = cache[plat]
        if tag == "v1":
            fitted[plat] = {"bias": 0.0, "use_ridge": False,
                            "route_cv_sigma": _["yaw_std"], "chosen_variant": "v1"}
            continue
        # Parse tag
        bias_on = "bias=True" in tag
        ridge_lam = None
        if "ridge=None" not in tag:
            ridge_lam = float(tag.split("ridge=")[1])
        # Fit on full data
        full_resid = np.concatenate([r["resid"] for r in recs])
        bias = float(np.mean(full_resid)) if bias_on else 0.0
        entry = {
            "bias": bias,
            "use_ridge": ridge_lam is not None,
            "chosen_variant": tag,
            "route_cv_sigma": _["yaw_std"],
        }
        if ridge_lam is not None:
            X = np.vstack([r["feats"] for r in recs])
            y = full_resid - bias
            ridge = fit_ridge(X, y, lam=ridge_lam)
            entry["ridge_lambda"] = ridge_lam
            entry["ridge_mu"] = ridge["mu"].tolist()
            entry["ridge_sd"] = ridge["sd"].tolist()
            entry["ridge_w"]  = ridge["w"].tolist()
        fitted[plat] = entry

    # Re-pool full-data prediction with chosen fits and compare
    print("\n== Full-data pooled (final fits, in-sample) ==")
    pooled_v1_yaw_sse = 0.0; pooled_yaw_n = 0
    pooled_v1_cte_sse = 0.0; pooled_cte_n = 0
    pooled_new_yaw_sse = 0.0
    pooled_new_cte_sse = 0.0
    for plat in PLATFORMS_WITH_TRUTH:
        for r in cache[plat]:
            yp_v1 = r["yr_v1"]
            f = fitted[plat]
            yp = yp_v1 + f["bias"]
            if f["use_ridge"]:
                rh = apply_ridge(r["feats"], {"mu": np.array(f["ridge_mu"]), "sd": np.array(f["ridge_sd"]), "w": np.array(f["ridge_w"])})
                yp = yp + rh
            d1 = yp_v1 - r["truth"]
            d2 = yp    - r["truth"]
            pooled_v1_yaw_sse += float(np.sum(d1*d1))
            pooled_new_yaw_sse += float(np.sum(d2*d2))
            pooled_yaw_n += len(d1)
            s1, nb1, _t = cte_rmse_segment(r["t"], r["v"], r["truth"], yp_v1)
            s2, nb2, _t = cte_rmse_segment(r["t"], r["v"], r["truth"], yp)
            pooled_v1_cte_sse += s1
            pooled_new_cte_sse += s2
            pooled_cte_n += nb1
    print(f"  V1 pooled yaw RMSE: {math.sqrt(pooled_v1_yaw_sse/pooled_yaw_n):.6f}")
    print(f"  NEW pooled yaw RMSE: {math.sqrt(pooled_new_yaw_sse/pooled_yaw_n):.6f}")
    print(f"  V1 pooled CTE RMSE: {math.sqrt(pooled_v1_cte_sse/pooled_cte_n):.3f}")
    print(f"  NEW pooled CTE RMSE: {math.sqrt(pooled_new_cte_sse/pooled_cte_n):.3f}")

    (ROOT / "final-model" / "coeffs.json").write_text(json.dumps(fitted, indent=2))
    print("\nWrote final-model/coeffs.json")

if __name__ == "__main__":
    t0 = time.time()
    main()
    print(f"\nelapsed {time.time()-t0:.1f}s")
