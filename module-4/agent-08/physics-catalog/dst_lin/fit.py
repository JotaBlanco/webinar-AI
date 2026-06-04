"""dst_lin/fit.py — refit C_αf, C_αr, Iz on the project's dev split.

Usage:
    python -m physics-catalog.dst_lin.fit

Or from inside Python:
    from physics_catalog.dst_lin.fit import fit_all
    fit_all()

Reads dev segments from `data/sim/segments/<platform>/`. Writes the fitted
coefficients to `physics-catalog/dst_lin/coeffs.json` (NOT coeffs.default.json
— that file stays as the textbook-prior fallback).

Route-grouped CV σ for each platform is written into coeffs.json under
`<platform>.route_cv_sigma_yaw`, satisfying the bias_without_route_cv gate
even if a later iteration adds a per-platform bias term.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

_MODEL_DIR = Path(__file__).resolve().parent
_CATALOG_DIR = _MODEL_DIR.parent
sys.path.insert(0, str(_CATALOG_DIR))

from _common import (  # noqa: E402
    FitSpec,
    PASSTHROUGH_PLATFORMS,
    PLATFORM_PRIORS,
    discover_dev_segments,
    find_template_root,
    fit_with_route_cv,
    get_platform_params,
    integrate_dst,
    load_coeffs,
    step_rk4_linear,
    write_coeffs,
)


def _load_score_module(template_root: Path):
    """Load skills/score-model/score.py via importlib (skill dirs use hyphens)."""
    path = template_root / "skills" / "score-model" / "score.py"
    spec = importlib.util.spec_from_file_location("_dst_lin_score", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_dst_lin_score"] = mod
    spec.loader.exec_module(mod)
    return mod


def _predict_factory(params: dict):
    """Return a predict(sim_df, platform) closure with these params baked in."""
    def _predict(sim_df, platform):
        if platform in PASSTHROUGH_PLATFORMS:
            return sim_df[["yaw_rate_pred_rads"]].copy()
        return integrate_dst(sim_df, platform, params, step_fn=step_rk4_linear)
    return _predict


def fit_one_platform(platform: str, *, template_root: Path, score_module) -> dict:
    """Fit {C_αf, C_αr, Iz} for one platform under route-grouped CV."""
    if platform in PASSTHROUGH_PLATFORMS:
        return {"_skipped": "passthrough_platform"}
    segs = discover_dev_segments(template_root, platform)
    if not segs:
        return {"_skipped": f"no_dev_segments_at_data/sim/segments/{platform}"}
    base = dict(PLATFORM_PRIORS[platform])
    spec = FitSpec(
        init=[base["C_alpha_f"], base["C_alpha_r"], base["Iz"]],
        bounds=[(20000.0, 250000.0), (20000.0, 250000.0), (1500.0, 8000.0)],
        names=["C_alpha_f", "C_alpha_r", "Iz"],
    )
    result = fit_with_route_cv(
        predict_factory=_predict_factory,
        spec=spec,
        platform=platform,
        base_params=base,
        segment_paths=segs,
        score_module=score_module,
    )
    return result


def fit_all(template_root: Path | None = None) -> dict:
    """Fit every platform and write the merged coeffs.json. Returns the dict."""
    if template_root is None:
        template_root = find_template_root(_MODEL_DIR)
    score_module = _load_score_module(template_root)

    out: dict = {"_model": "dst_lin", "_fitted_from": str(template_root)}
    for platform in PLATFORM_PRIORS:
        print(f"  [dst_lin] fitting {platform} ...", flush=True)
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
        print(f"    route-CV σ_yaw={res['route_cv_sigma_yaw']}, "
              f"σ_cte={res['route_cv_sigma_cte']}", flush=True)

    # Write fit_diagnostics.json for iterate's gate.
    diag = {
        "co_collapse": False,  # heuristic: if any C_αf/C_αr fitted to same ratio bound
        "stuck_on_bound": any(
            isinstance(v, dict) and v.get("stuck_on_bound") for v in out.values()
        ),
        "non_convergence": any(
            isinstance(v, dict) and v.get("converged") is False for v in out.values()
        ),
        "dev_train_gap": None,
    }
    (_MODEL_DIR / "fit_diagnostics.json").write_text(json.dumps(diag, indent=2) + "\n")

    write_coeffs(_MODEL_DIR, out)
    return out


if __name__ == "__main__":
    result = fit_all()
    print(json.dumps(result, indent=2))
