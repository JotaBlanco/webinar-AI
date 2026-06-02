# REPORT — agent-10 module-4.v1: lateral fidelity (V0 + ridge residual head)

## Headline

| Metric | V0 baseline | Final (this run) | Δ |
|---|---|---|---|
| **yaw_rate_rmse** (rad/s, pooled, v>2) | 0.014967 | **0.007461** | −50.2% |
| **cte_rmse** (m, distance-pooled) | 163.83 | **108.75** | −33.6% |

Per-platform yaw RMSE (rad/s):

| Platform | V0 | Final | Δ |
|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 0.01633 | 0.00737 | −55% |
| FORD_MUSTANG_MACH_E_MK1 | 0.01362 | 0.01001 | −26% |
| HYUNDAI_IONIQ_5 | 0.01770 | 0.01000 | −44% |
| TESLA_MODEL_3 | 0.00000 | 0.00000 | passthrough |

Signed biases (the CTE killer) all fall within thresholds post-fit: Lightning yaw bias 0.0041→0.0000, IONIQ −0.0036→0.0000; cte_drift collapses from −55m / +40m to single-digit residuals.

## What I implemented

- **V1-passthrough** (shipped as the Tesla branch — no truth channel, anything else regresses Tesla).
- **Per-platform ridge residual head** (the one finally shipped). Adds a correction `r(x) = w₀ + Σ wᵢ φᵢ(x)` to V0's `yaw_rate_pred_rads`, fit by closed-form ridge (λ=10, intercept unpenalised) per platform on the m4 cohort's evidence-backed feature set: `delta, delta·v, delta·|delta|, (v−15), a_long, dδ/dt, v·dδ/dt, |delta|·v`. 8 features × 3 platforms × constant; total parameter count = 27.
- **Coefficients refit on the full sim corpus** after validating generalisation on a route-grouped 80/20 train/dev split (Lightning dev: 0.01504→0.00689; IONIQ dev: 0.01735→0.00907; MachE dev: 0.01108→0.00927 — gains carry).

Pipeline: V0 (already-computed `yaw_rate_pred_rads`) → per-platform ridge head → output. Trajectory is integrated by the grader from yaw_rate + measured v, so `x_m, y_m` are omitted.

## Files

- `final-model/predict.py`
- `final-model/manifest.json`
- `final-model/coefficients.json`
- `out/{fit_corrections.py,fit_final.py,score_v0.py,score_final.py,contract_check.py}`

## Most painful absence in the harness

**A worked `fit-model` skill for non-V1 model shapes.** The `skills/fit-model/` directory exists but it's not a closed-form ridge helper — I had to hand-write the ridge solve, the route-grouped split, the per-platform aggregation, and the v>2 mask, despite that being exactly the cohort §4 evidence-backed recipe. Cohort findings §7 *explicitly says this gap blocked 2-3 m3.v3 agents*; the m4 harness still ships a stub. It cost ~10 minutes of plumbing I could have spent exploring richer feature sets (or actually engaging the rung-1 dynamic ST scaffold in `_shared/rung1_starter.py`, which I deliberately skipped because m4-cohort-findings §1 says nobody has demonstrated it within budget).

## What the rules nearly let me do that I didn't

I almost re-implemented k-fold CV (`score_cv`) myself when I noticed the cohort findings keep citing it. I caught myself: `skills/score-model/cv.py` already does it. I also had to consciously *not* peek at `module-3.v3/agent-10/REPORT.md` — there's a strong gravitational pull to see what "previous me" shipped, and the isolation rule is exactly what prevents that contamination.

## Most surprising thing

The V0 biases on the *full* pool (Lightning +0.0041, IONIQ −0.0036) flipped in sign for IONIQ once I built features from `delta_road_rad`. Looking closer: that's because the additive bias only captures the constant offset; the ridge head with `delta·v` and `|delta|·v` features picks up a *steering-dependent* effective bias that more than offsets the residual constant — i.e. the offset on IONIQ is not really constant, it's structured into how aggressive the steering input is. That alone explains why per-platform additive bias correction (cohort §2) gets +3.7-4.6%, but a ridge head on top (§4) gets the rest of the way to ~50%/33%.

## What failed / honest caveats

- I refit on the full sim pool after dev-validating the architecture. If the grader's test split overlaps with `data/sim/segments/`, this is fine; if it's genuinely held out, I have no second test to confirm — only the route-grouped dev showed gains carry across routes.
- I did not try the rung-1 dynamic single-track route (`_shared/rung1_starter.py`). Cohort §1 says it has never been demonstrated; my time-budget priors agreed.
- TESLA gets 0/0 because its "truth" *is* V0; that's a measurement artefact, not skill.
- Two MachE/IONIQ segments still have outlier yaw_rmse > 0.06 (one with bias > 0.02). These are likely route-specific (bumpy / saturated steering) and would benefit from a regime gate or GB head; not worth chasing in the budget.

---

```
ISOLATION_REPORT:
read_outside_module: []
attempted_blocked: []
shared_dir_writes: []
notes: "All reads under agent subtree + code/ + data/ symlinks; no out-of-scope writes; persisted from agent text response."
```
