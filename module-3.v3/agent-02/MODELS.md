# MODELS.md — registry of candidate models

One `##`-level entry per candidate. Add entries as you build models under
`models/<name>/`. **Preflight requires ≥3 entries with ≥1 tagged
`structure: differs-from-v1`.** See `AGENTS.md` § "Models as first-class objects".

Schema (every field expected; preflight scans for them):

```
## <model-name>
- dir: models/<model-name>/
- structure: differs-from-v1 | refines-v1
- status: drafting | assessed | shipped | shelved
- pooled-yaw-rmse-dev: <number or pending>
- pooled-cte-rmse-dev: <number or pending>
- verdict: <one line — what to do with this candidate and why>
```

`structure:` tells the cohort whether your model attacks V1 structurally or just
re-fits its shape:

- `differs-from-v1` — the model has a state-space, integrator, or formulation V1
  cannot reach by re-fitting coefficients. Examples: dynamic single-track ODE,
  residual learner on V1's output, regime-switched composite, complementary
  filter, nonlinear tyre. **Most of your candidates should be tagged this way.**
- `refines-v1` — same kinematic-single-track shape as V1 with different fits.
  Useful as a sanity check (a coefficient refit shouldn't beat V1 by much) but
  shipping one of these is the m3.v2 failure mode.

V1's pooled-dev scores for comparison: `yaw_rmse = 0.005874 rad/s`, `cte_rmse = 56.81 m`.

---

## affine-postcorrection
- dir: models/affine-postcorrection/
- structure: differs-from-v1
- status: assessed
- pooled-yaw-rmse-dev: 0.01053
- pooled-cte-rmse-dev: 72.53
- verdict: KEEP — most of the available CTE win comes from the per-platform bias term. Captures ~95% of the structural improvement on its own.

## saturation-correction
- dir: models/saturation-correction/
- structure: differs-from-v1
- status: assessed
- pooled-yaw-rmse-dev: 0.01053
- pooled-cte-rmse-dev: 72.61
- verdict: SHELVE — cubic-in-a_lat term co-collapses with affine `a`. OLS absorbs nearly all of the residual into linear scale; nonlinear feature buys < 0.05% pooled.

## v1-plus-residual-features
- dir: models/v1-plus-residual-features/
- structure: differs-from-v1
- status: shipped
- pooled-yaw-rmse-dev: 0.01052
- pooled-cte-rmse-dev: 72.61
- verdict: SHIPPED — affine + saturation + steering-rate (d delta/dt). Marginally best pooled. Steering-rate is the only structurally novel feature beyond affine; gives a small but real signal on Mach-E (d=-0.022) consistent with V1's tau-pole under-modelling transient dynamics.
