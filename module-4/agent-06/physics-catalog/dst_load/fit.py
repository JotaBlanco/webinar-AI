"""dst_load/fit.py — fit {C_alpha_f, C_alpha_r, Iz, h_cg} on dev."""

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
    FitSpec, PASSTHROUGH_PLATFORMS, PLATFORM_PRIORS,
    discover_dev_segments, find_template_root, fit_with_route_cv,
    integrate_dst, step_rk4_tyre, write_coeffs,
)
from predict import _load_tyre  # noqa: E402


def _load_score_module(template_root: Path):
    path = template_root / "skills" / "score-model" / "score.py"
    spec = importlib.util.spec_from_file_location("_dst_load_score", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_dst_load_score"] = mod
    spec.loader.exec_module(mod)
    return mod


def _predict_factory(params: dict):
    def _predict(sim_df, platform):
        if platform in PASSTHROUGH_PLATFORMS:
            return sim_df[["yaw_rate_pred_rads"]].copy()
        p_local = dict(PLATFORM_PRIORS[platform])
        p_local.update({k: v for k, v in params.items()
                        if isinstance(v, (int, float)) and not isinstance(v, bool)})
        return integrate_dst(sim_df, platform, p_local,
                             step_fn=step_rk4_tyre, tyre_fn=_load_tyre)
    return _predict


def fit_one_platform(platform: str, *, template_root: Path, score_module) -> dict:
    if platform in PASSTHROUGH_PLATFORMS:
        return {"_skipped": "passthrough_platform"}
    segs = discover_dev_segments(template_root, platform)
    if not segs:
        return {"_skipped": f"no_dev_segments_at_data/sim/segments/{platform}"}
    base = dict(PLATFORM_PRIORS[platform])
    spec = FitSpec(
        init=[base["C_alpha_f"], base["C_alpha_r"], base["Iz"], base["h_cg"]],
        bounds=[(20000.0, 250000.0), (20000.0, 250000.0), (1500.0, 8000.0), (0.30, 1.20)],
        names=["C_alpha_f", "C_alpha_r", "Iz", "h_cg"],
    )
    return fit_with_route_cv(
        predict_factory=_predict_factory,
        spec=spec, platform=platform,
        base_params=base, segment_paths=segs,
        score_module=score_module,
    )


def fit_all(template_root: Path | None = None) -> dict:
    if template_root is None:
        template_root = find_template_root(_MODEL_DIR)
    score_module = _load_score_module(template_root)
    out = {"_model": "dst_load", "_fitted_from": str(template_root)}
    for platform in PLATFORM_PRIORS:
        print(f"  [dst_load] fitting {platform} ...", flush=True)
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
