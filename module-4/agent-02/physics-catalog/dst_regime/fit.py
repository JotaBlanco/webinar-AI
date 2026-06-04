"""dst_regime/fit.py — fit {C_αf, C_αr, Iz, theta_v_psi, blend_width} on dev."""

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
    FitSpec,
    PASSTHROUGH_PLATFORMS,
    PLATFORM_PRIORS,
    discover_dev_segments,
    find_template_root,
    fit_with_route_cv,
    write_coeffs,
)
import predict as _predict_mod  # noqa: E402


def _load_score_module(template_root: Path):
    path = template_root / "skills" / "score-model" / "score.py"
    spec = importlib.util.spec_from_file_location("_dst_regime_score", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_dst_regime_score"] = mod
    spec.loader.exec_module(mod)
    return mod


def _predict_factory(params: dict):
    """Bind params into the predict by writing them into a small temp coeffs file
    via monkey-patching the load_coeffs call inside predict.py."""
    import _common as common

    def _predict(sim_df, platform):
        if platform in PASSTHROUGH_PLATFORMS:
            return sim_df[["yaw_rate_pred_rads"]].copy()
        # Build per-platform params merging fitted values over the prior.
        p_local = dict(PLATFORM_PRIORS[platform])
        p_local.update({k: v for k, v in params.items()
                        if isinstance(v, (int, float)) and not isinstance(v, bool)})
        # Call the same blend logic the predict uses, but with our params.
        theta = float(p_local.get("theta_v_psi", 3.5))
        width = float(p_local.get("blend_width", 0.5))
        dst_out = common.integrate_dst(sim_df, platform, p_local,
                                       step_fn=common.step_rk4_linear)
        dst_yaw = dst_out["yaw_rate_pred_rads"].to_numpy()
        kin_yaw = _predict_mod._v1_kinematic_yaw(sim_df, platform)
        import numpy as np
        v = sim_df["v_mps"].to_numpy()
        gate_var = np.abs(v * sim_df["yaw_rate_pred_rads"].to_numpy())
        gate = _predict_mod._smooth_gate(gate_var, theta, width)
        blended = gate * dst_yaw + (1.0 - gate) * kin_yaw
        floor_mask = v < common.V_FLOOR_MPS
        blended = np.where(floor_mask, sim_df["yaw_rate_pred_rads"].to_numpy(), blended)
        out = sim_df[["yaw_rate_pred_rads"]].copy()
        out["yaw_rate_pred_rads"] = blended
        return out
    return _predict


def fit_one_platform(platform: str, *, template_root: Path, score_module) -> dict:
    if platform in PASSTHROUGH_PLATFORMS:
        return {"_skipped": "passthrough_platform"}
    segs = discover_dev_segments(template_root, platform)
    if not segs:
        return {"_skipped": f"no_dev_segments_at_data/sim/segments/{platform}"}
    base = dict(PLATFORM_PRIORS[platform])
    base["theta_v_psi"] = 3.5
    base["blend_width"] = 0.5
    spec = FitSpec(
        init=[base["C_alpha_f"], base["C_alpha_r"], base["Iz"],
              base["theta_v_psi"], base["blend_width"]],
        bounds=[(20000.0, 250000.0), (20000.0, 250000.0), (1500.0, 8000.0),
                (0.5, 8.0), (0.1, 2.0)],
        names=["C_alpha_f", "C_alpha_r", "Iz", "theta_v_psi", "blend_width"],
    )
    return fit_with_route_cv(
        predict_factory=_predict_factory,
        spec=spec,
        platform=platform,
        base_params=base,
        segment_paths=segs,
        score_module=score_module,
    )


def fit_all(template_root: Path | None = None) -> dict:
    if template_root is None:
        template_root = find_template_root(_MODEL_DIR)
    score_module = _load_score_module(template_root)
    out: dict = {"_model": "dst_regime", "_fitted_from": str(template_root)}
    for platform in PLATFORM_PRIORS:
        print(f"  [dst_regime] fitting {platform} ...", flush=True)
        res = fit_one_platform(platform, template_root=template_root,
                               score_module=score_module)
        if "_skipped" in res:
            out[platform] = {"_skipped": res["_skipped"]}; continue
        params = res["params"]
        out[platform] = {
            **params,
            "route_cv_sigma_yaw": res["route_cv_sigma_yaw"],
            "route_cv_sigma_cte": res["route_cv_sigma_cte"],
            "n_segments": res["n_segments"],
            "n_routes": res["n_routes"],
            "stuck_on_bound": res["stuck_on_bound"],
            "converged": res["converged"],
            "final_loss": res["final_loss"],
        }
    diag = {
        "stuck_on_bound": any(
            isinstance(v, dict) and v.get("stuck_on_bound") for v in out.values()
        ),
        "non_convergence": any(
            isinstance(v, dict) and v.get("converged") is False for v in out.values()
        ),
        "co_collapse": False,
        "dev_train_gap": None,
    }
    (_MODEL_DIR / "fit_diagnostics.json").write_text(json.dumps(diag, indent=2) + "\n")
    write_coeffs(_MODEL_DIR, out)
    return out


if __name__ == "__main__":
    print(json.dumps(fit_all(), indent=2))
