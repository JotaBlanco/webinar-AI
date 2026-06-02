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

## v1-steerrate-ff
- dir: models/v1-steerrate-ff/
- structure: differs-from-v1
- status: shelved
- pooled-yaw-rmse-dev: ~0.0058 (subset)
- pooled-cte-rmse-dev: ~unchanged
- verdict: shelved — `k_dd · d(delta)/dt` feedforward bought ≤0.7% yaw and ≈0% CTE per platform on subset; sign of k_dd flipped to negative on Mach-E suggesting np.gradient phase artefacts rather than real lag. A scalar steering-derivative is not the right structural attack on the transient residual.

## v1-asym-gain
- dir: models/v1-asym-gain/
- structure: differs-from-v1
- status: assessed
- pooled-yaw-rmse-dev: 0.005844
- pooled-cte-rmse-dev: 56.035
- verdict: assessed — direction-asymmetric steering gain (g_left ≠ g_right) cuts yaw bias on Mach-E and IONIQ-5 to near zero. Small pooled win (-0.5% yaw, -1.4% CTE). Kept as the gain layer for the shipped model.

## v1-asym-debias
- dir: models/v1-asym-debias/
- structure: differs-from-v1
- status: shipped
- pooled-yaw-rmse-dev: 0.005805
- pooled-cte-rmse-dev: 54.689
- verdict: **shipped.** Asymmetric gain + gated additive yaw-bias offset (zero on Lightning by design, half-strength on Mach-E/IONIQ-5 to guard against subset overfit). Pooled: -1.2% yaw, -3.7% CTE. Mach-E cte_drift cut from -22 m to -5 m; IONIQ-5 from -12 m to -6 m. Clears all bias-warning 🚨 flags V1 carried.
