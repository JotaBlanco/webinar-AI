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

## bias-corrected-v1
- dir: models/bias-corrected-v1/
- structure: differs-from-v1
- status: shipped
- pooled-yaw-rmse-dev: 0.005843
- pooled-cte-rmse-dev: 54.189
- verdict: SHIP. V1 + per-platform additive yaw bias (Mach-E +0.00210, IONIQ +0.00108). CTE −4.6% vs V1; yaw essentially unchanged. Smallest possible structural delta over V1.

## steering-derivative-residual
- dir: models/steering-derivative-residual/
- structure: differs-from-v1
- status: assessed
- pooled-yaw-rmse-dev: 0.005827
- pooled-cte-rmse-dev: 54.509
- verdict: shelve. Per-platform linear residual on (dδ/dt, v·dδ/dt, sign·sqrt). Yaw fractionally better than bias-corrected; CTE fractionally worse. Complexity unjustified.

## v-dependent-lag
- dir: models/v-dependent-lag/
- structure: differs-from-v1
- status: shelved
- pooled-yaw-rmse-dev: 0.005871
- pooled-cte-rmse-dev: 56.741
- verdict: shelve. Grid search collapsed Mach-E and Lightning back to V1's scalar τ; only IONIQ picked up a non-trivial τ1=0.05 with negligible gain. Rules out v-dependent lag as the missing structure.
