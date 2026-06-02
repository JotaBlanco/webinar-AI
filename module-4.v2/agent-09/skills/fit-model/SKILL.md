---
name: fitting-model
description: Optimise per-platform coefficient dicts of an opaque model by minimising a chosen objective — pooled yaw-rate RMSE (rad/s), pooled CTE RMSE (m), or a yaw+CTE blend. The fitter is model-agnostic — the agent supplies a `predict_factory(platform, coeffs) -> callable(sim_df) -> ndarray`; the skill calls it and runs scipy.optimize.minimize. Fits each platform independently. Truth columns and the V0 baseline alias are resolved via `scoring-model`'s `PLATFORM_SCHEMA`, so Tesla and any platform with a non-default schema fit cleanly. Use this when `scoring-model` is showing systematic per-platform bias and you want the calibration auto-tuned against the same KPI the canonical grader uses.
when-to-invoke: You have a parametrised predictor and want its coefficients optimised against yaw RMSE, CTE RMSE, or a blend — without writing the scipy/optimisation glue yourself. Especially useful when the bias-warnings block of `scoring-model` is lit up and you need a CTE-aware fit (yaw-RMSE-only fits leave the integrated drift on the table).
when-NOT-to-invoke: You only want to score a model (use scoring-model); you only want to diff two models (use compare-models); you need a global / cross-platform fit (this skill fits each platform independently — change the loop in `fit.py` if you need joint).
inputs: predict_factory (callable[platform, coeffs] -> callable[sim_df] -> ndarray), initial_coeffs ({platform: {param: float}}), train_segments (list[Path] or {platform: [Path]}), objective ("yaw" | "cte" | "yaw_plus_cte"), dev_segments (optional), bounds (optional per-platform per-param), method (scipy method or None for auto), max_iter, sample_filter_v_mps, grid_step_m, min_distance_m, cte_weight, verbose.
outputs: dict — coeffs (fitted), train_obj, dev_obj, gap (dev-train), gap_fraction, warnings (co-collapse / overfit / stuck-on-bound / non-convergence per platform), history (per-iteration trace), n_iter, converged, objective.
load-cost: ~230 tokens metadata, ~520 tokens body.
---

# fitting-model

## What it does

Given a parametrised predictor and an objective, fit the parameters per platform with scipy.optimize.

The fitter does NOT know what your model is. The agent supplies a `predict_factory`:

```python
def predict_factory(platform: str, coeffs: dict[str, float]):
    def predict(sim_df) -> np.ndarray:
        # any model the agent likes — bicycle, understeer, cubic, lookup table.
        # Returns yaw-rate predictions aligned with sim_df.
        ...
    return predict
```

`fit()` calls `predict_factory(platform, current_coeffs)` once per scipy iteration, evaluates the objective over that platform's pre-loaded segments, and steps the parameter vector. Per platform. Independently.

The agent is free to:

- Change the model structure between calls (V1 yaw factor → V2 understeer → V3 lookup table) — just rebuild the factory and `initial_coeffs`.
- Use a different parameter set on each platform (Tesla can be `{}` if you want it to no-op).
- Wrap a per-segment feature mask, time-varying coefficient, anything.

## Post-fit diagnostics

`fit()` runs four cheap checks on every platform's fit and surfaces them as `result["warnings"][platform]`. `format_fit_summary()` opens with them — they are the first thing you see, before the per-platform table — because the optimiser cannot detect any of these on its own. The categories:

- **`co_collapse`** (🚨 high) — two or more parameters started non-zero and ended near zero. Usual cause: co-degenerate parameterisation (e.g. `gain` and `L_eff` both free with no anchor), where the optimiser finds a numerically-equivalent but physically nonsensical solution. Fix: remove one parameter, fix one, or add a physical bound.
- **`stuck_on_bound`** (⚠️ warn) — a fitted value sits within 2% of a supplied bound's range. The true optimum may be outside the bound; widen carefully or confirm this is the physical limit you intended.
- **`wide_train_dev_gap`** (⚠️ warn / 🚨 high) — `dev_obj > (1 + OVERFIT_GAP_FRACTION) × train_obj` (default 50% gap warns; 100% high). Suggests overfit, route leakage, or model too flexible. Tune the model down, regularise, or check the split.
- **`did_not_converge`** (⚠️ warn) — scipy returned `success=False`. Compare train vs dev before trusting.

Thresholds are module-level constants (`COLLAPSE_REL_THRESHOLD`, `COLLAPSE_ABS_THRESHOLD`, `OVERFIT_GAP_FRACTION`, `NEAR_BOUND_FRACTION`). Edit if your problem's natural scale is different.

## Train/dev gap is displayed inline

When `dev_segments` is passed, `format_fit_summary()`'s table grows three columns — `dev_obj`, `gap`, `gap_%` — and inline-flags any `gap_%` above `OVERFIT_GAP_FRACTION`. This is the difference between "I fit the train set perfectly" and "I shipped a model that generalises". Pass dev segments.

## Bounds are encouraged

Default method is Nelder-Mead (no bounds). It's robust but it will happily find degenerate solutions when two parameters are non-identifiable. **If you have any physical intuition about your parameters' scale, pass `bounds`** — the method switches to L-BFGS-B and the `co_collapse` failure mode collapses (heh) to "stuck_on_bound", which is much easier to read.

A reasonable shape for a single-track / understeer fit:

```python
bounds = {
    plat: {
        "L_eff": (1.5, 5.0),     # wheelbase metres
        "K_us":  (0.0, 0.01),    # understeer coefficient
        "gain":  (0.5, 1.5),     # multiplicative correction
        "bias":  (-0.05, 0.05),  # rad/s zero-offset
    }
    for plat in PLATFORMS
}
```

## Why this exists

The M2 cohort fit per-sample yaw residuals and hoped CTE came along. CTE is dominated by *systematic bias*, not RMS noise — fitting yaw-RMSE leaves the integrated drift on the table. `fitting-model` lets you optimise against `cte` directly (or `yaw_plus_cte`) without rewriting your model code.

It also collapses the "write scipy glue, plumb pre-loaded segments, handle the per-platform schema" boilerplate that every M2 agent re-implemented by hand.

## Objectives

- `"yaw"`          — pooled, v-filtered yaw-rate RMSE (rad/s). Matches the score-model headline.
- `"cte"`          — pooled distance-bin CTE RMSE (m). Matches the score-model headline.
- `"yaw_plus_cte"` — `yaw_rmse + cte_weight * (cte_rmse / 1000)`. CTE is divided by 1000 so the two metrics land on a comparable scale; tune `cte_weight` to bias the fit.

## Schema-awareness

The fitter reuses `PLATFORM_SCHEMA` from `scoring-model` to resolve each platform's truth column and to alias the V0 baseline into `sim_df["yaw_rate_pred_rads"]`. So Tesla's `psi_dot_rads` truth and its missing baseline column are handled identically to Ford/Hyundai. To add a platform or fix a column rename, edit `scoring-model/score.py`'s `PLATFORM_SCHEMA` — both skills pick it up.

## Usage

A minimal V1 affine fit (per-platform `a * yaw_rate_pred + b`), trained for CTE:

```python
from pathlib import Path
import numpy as np
from skills.fit_model.fit import fit, format_fit_summary

def predict_factory(platform, coeffs):
    a, b = coeffs["a"], coeffs["b"]
    def predict(sim_df):
        return a * sim_df["yaw_rate_pred_rads"].to_numpy() + b
    return predict

init = {plat: {"a": 1.0, "b": 0.0} for plat in
        ("FORD_F_150_LIGHTNING_MK1", "FORD_MUSTANG_MACH_E_MK1", "HYUNDAI_IONIQ_5")}
train = sorted(Path("data/sim/segments").glob("*/**/sim.csv"))[:30]
dev   = sorted(Path("data/sim/segments").glob("*/**/sim.csv"))[30:40]

result = fit(predict_factory, init, train_segments=train,
             objective="cte", dev_segments=dev, verbose=True)
print(format_fit_summary(result))

# `result["coeffs"]` is what you'd persist into `final-model/coeffs.json`.
```

## Method choice

- No bounds → `Nelder-Mead` (derivative-free, robust to noisy objectives, ~50–200 calls per platform).
- With bounds → `L-BFGS-B` (finite-difference gradients, faster when smooth).
- Override with `method=...` if you know better (e.g. `"Powell"` for ill-conditioned problems).

## What it does not do

- It does not pick the model. You bring the predictor.
- It does not pool across platforms. Fits are independent. If you want a shared parameter across platforms, optimise it yourself or modify `fit.py`.
- It does not handle gradients. Bring `bounds` to use `L-BFGS-B`, but the gradient is finite-difference; if your model has discontinuities, stay with Nelder-Mead.
- It does not validate generalisation for you. Pass `dev_segments` to get a held-out number; pick your own train/dev split (`make-train-dev-split`).

## Smoke test

`python3 _smoke.py` — fits a 2-param affine V0 correction (`a * v0_pred + b`) per platform on a handful of segments, against the `cte` objective, and asserts that the fitted residual is strictly lower than V0's residual on the train set.

## Extending this skill

- Joint fit across platforms: replace the per-platform loop with a single `minimize` call over a stacked parameter vector. Add a `joint=True` argument.
- Regularisation: add `lambda * ||coeffs - prior||²` to `_evaluate()` and pass a `prior` arg.
- Different objective: add a branch to `_evaluate()` (e.g. weighted by route distance).
- Different optimiser: pick any from `scipy.optimize` and pass via `method=`.
