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

## v1-plus-resid
- dir: models/v1-plus-resid/
- structure: differs-from-v1
- status: shipped
- pooled-yaw-rmse-dev: 0.005727
- pooled-cte-rmse-dev: 54.304
- verdict: SHIPPED. Wins on yaw RMSE outright (−2.5% vs V1) and closes ≈90% of the CTE-drift gap that V1 leaves on Mach-E and IONIQ-5. R² of the residual fit is only 0.02–0.07, but that's enough to scrub the bias structure that drives pooled CTE.

## steer-rate-ff
- dir: models/steer-rate-ff/
- structure: differs-from-v1
- status: assessed
- pooled-yaw-rmse-dev: 0.005832
- pooled-cte-rmse-dev: 54.462
- verdict: Shelved in favour of v1-plus-resid. Beats V1 on both KPIs (−0.7% yaw, −4.1% CTE) but the derivative term only explains a small fraction of the residual; most of the improvement actually comes from its additive bias term.

## v1-cte-debiased
- dir: models/v1-cte-debiased/
- structure: differs-from-v1
- status: assessed
- pooled-yaw-rmse-dev: 0.005843
- pooled-cte-rmse-dev: 54.188
- verdict: Shelved in favour of v1-plus-resid. Beats V1 (−0.5% yaw, −4.6% CTE), and is the best on CTE alone, but loses to v1-plus-resid on yaw RMSE. Confirms that the bulk of the CTE-gap-vs-V1 lives in a single platform-level offset.
