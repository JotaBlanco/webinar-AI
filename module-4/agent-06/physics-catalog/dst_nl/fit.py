"""dst_nl/fit.py — refit {C_αf, C_αr, Iz, mu, C_pacejka} on dev split."""

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
    integrate_dst,
    step_rk4_tyre,
    write_coeffs,
)
from predict import _pacejka_tyre  # noqa: E402


def _load_score_module(template_root: Path):
    path = template_root / "skills" / "score-model" / "score.py"
    spec = importlib.util.spec_from_file_location("_dst_nl_score", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_dst_nl_score"] = mod
    spec.loader.exec_module(mod)
    return mod


def _predict_factory(params: dict):
    def _predict(sim_df, platform):
        if platform in PASSTHROUGH_PLATFORMS:
            return sim_df[["yaw_rate_pred_rads"]].copy()
        return integrate_dst(
            sim_df, platform, params,
            step_fn=step_rk4_tyre,
            tyre_fn=_pacejka_tyre,
        )
    return _predict


def fit_one_platform(platform: str, *, template_root: Path, score_module) -> dict:
    if platform in PASSTHROUGH_PLATFORMS:
        return {"_skipped": "passthrough_platform"}
    segs = discover_dev_segments(template_root, platform)
    if not segs:
        return {"_skipped": f"no_dev_segments_at_data/sim/segments/{platform}"}
    base = dict(PLATFORM_PRIORS[platform])
    base["mu"] = 0.9
    base["C_pacejka"] = 1.30
    spec = FitSpec(
        init=[base["C_alpha_f"], base["C_alpha_r"], base["Iz"],
              base["mu"], base["C_pacejka"]],
        bounds=[(20000.0, 250000.0), (20000.0, 250000.0), (1500.0, 8000.0),
                (0.5, 1.3), (1.0, 1.8)],
        names=["C_alpha_f", "C_alpha_r", "Iz", "mu", "C_pacejka"],
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

    out: dict = {"_model": "dst_nl", "_fitted_from": str(template_root)}
    for platform in PLATFORM_PRIORS:
        print(f"  [dst_nl] fitting {platform} ...", flush=True)
        res = fit_one_platform(platform, template_root=template_root,
                               score_module=score_module)
        if "_skipped" in res:
            print(f"    SKIPPED: {res['_skipped']}", flush=True)
            out[platform] = {"_skipped": res["_skipped"]}
            continue
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
        print(f"    fitted: {params}", flush=True)

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
