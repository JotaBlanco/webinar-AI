"""dst_combined_slip/fit.py — fit {C_αf, C_αr, Iz, mu, alpha_drive}."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_MODEL_DIR = Path(__file__).resolve().parent
_CATALOG_DIR = _MODEL_DIR.parent
sys.path.insert(0, str(_CATALOG_DIR))
sys.path.insert(0, str(_MODEL_DIR))

from _common import (  # noqa: E402
    FitSpec, PASSTHROUGH_PLATFORMS, PLATFORM_PRIORS, V_FLOOR_MPS,
    discover_dev_segments, find_template_root, fit_with_route_cv, write_coeffs,
)
import predict as _predict_mod  # noqa: E402


def _load_score_module(template_root: Path):
    path = template_root / "skills" / "score-model" / "score.py"
    spec = importlib.util.spec_from_file_location("_dst_combined_score", str(path))
    mod = importlib.util.module_from_spec(spec); sys.modules["_dst_combined_score"] = mod
    spec.loader.exec_module(mod); return mod


def _predict_factory(params: dict):
    import numpy as np
    def _predict(sim_df, platform):
        if platform in PASSTHROUGH_PLATFORMS:
            return sim_df[["yaw_rate_pred_rads"]].copy()
        p_local = dict(PLATFORM_PRIORS[platform])
        p_local.update({k: v for k, v in params.items()
                        if isinstance(v, (int, float)) and not isinstance(v, bool)})
        import pandas as pd
        t = sim_df["t_s"].to_numpy(); delta = sim_df["delta_road_rad"].to_numpy()
        v = sim_df["v_mps"].to_numpy()
        a_long = sim_df.get("a_long_mps2", pd.Series(np.zeros(len(t)))).to_numpy()
        yaw_v0 = sim_df["yaw_rate_pred_rads"].to_numpy()
        n = len(t); psi_dot = np.zeros(n)
        state = np.array([0.0, yaw_v0[0] if n > 0 else 0.0])
        psi_dot[0] = state[1]
        for i in range(1, n):
            dt = max(t[i] - t[i - 1], 1e-3)
            if v[i] < V_FLOOR_MPS:
                state = np.array([0.0, yaw_v0[i]]); psi_dot[i] = yaw_v0[i]; continue
            state = _predict_mod._combined_slip_step(
                state, float(delta[i]), float(v[i]), float(a_long[i]), p_local, dt
            )
            if not np.all(np.isfinite(state)):
                state = np.array([0.0, yaw_v0[i]])
            psi_dot[i] = state[1]
        out = sim_df[["yaw_rate_pred_rads"]].copy()
        out["yaw_rate_pred_rads"] = psi_dot
        return out
    return _predict


def fit_one_platform(platform: str, *, template_root: Path, score_module) -> dict:
    if platform in PASSTHROUGH_PLATFORMS:
        return {"_skipped": "passthrough_platform"}
    segs = discover_dev_segments(template_root, platform)
    if not segs:
        return {"_skipped": f"no_dev_segments_at_data/sim/segments/{platform}"}
    base = dict(PLATFORM_PRIORS[platform])
    base["mu"] = 0.9
    # Lightning is the F-150 EV (RWD-biased), others mostly AWD-ish; start neutral.
    base["alpha_drive"] = 0.3 if "LIGHTNING" in platform else 0.5
    spec = FitSpec(
        init=[base["C_alpha_f"], base["C_alpha_r"], base["Iz"], base["mu"], base["alpha_drive"]],
        bounds=[(20000.0, 250000.0), (20000.0, 250000.0), (1500.0, 8000.0), (0.5, 1.2), (0.0, 1.0)],
        names=["C_alpha_f", "C_alpha_r", "Iz", "mu", "alpha_drive"],
    )
    return fit_with_route_cv(
        predict_factory=_predict_factory, spec=spec, platform=platform,
        base_params=base, segment_paths=segs, score_module=score_module,
    )


def fit_all(template_root: Path | None = None) -> dict:
    if template_root is None:
        template_root = find_template_root(_MODEL_DIR)
    score_module = _load_score_module(template_root)
    out = {"_model": "dst_combined_slip", "_fitted_from": str(template_root)}
    for platform in PLATFORM_PRIORS:
        print(f"  [dst_combined_slip] fitting {platform} ...", flush=True)
        res = fit_one_platform(platform, template_root=template_root, score_module=score_module)
        if "_skipped" in res:
            out[platform] = {"_skipped": res["_skipped"]}; continue
        params = res["params"]
        out[platform] = {
            **params,
            "route_cv_sigma_yaw": res["route_cv_sigma_yaw"],
            "route_cv_sigma_cte": res["route_cv_sigma_cte"],
            "n_segments": res["n_segments"], "n_routes": res["n_routes"],
            "stuck_on_bound": res["stuck_on_bound"], "converged": res["converged"],
            "final_loss": res["final_loss"],
        }
    diag = {
        "stuck_on_bound": any(isinstance(v, dict) and v.get("stuck_on_bound") for v in out.values()),
        "non_convergence": any(isinstance(v, dict) and v.get("converged") is False for v in out.values()),
        "co_collapse": False, "dev_train_gap": None,
    }
    (_MODEL_DIR / "fit_diagnostics.json").write_text(json.dumps(diag, indent=2) + "\n")
    write_coeffs(_MODEL_DIR, out)
    return out


if __name__ == "__main__":
    print(json.dumps(fit_all(), indent=2))
