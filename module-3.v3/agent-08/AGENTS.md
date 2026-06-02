# AGENTS.md — Module 3 v3 (beyond V1: structurally-different lateral-fidelity models)

You are working on the lateral-fidelity challenge. The two KPIs are in your task prompt: pooled yaw-rate RMSE and distance-resampled cross-track-error RMSE. The job in m3.v3 is **not** to fit better coefficients to the kinematic single-track — that ceiling is already shipped as V1.

## What is V1, and why it changes how you should work

`code/v1_baseline.py` is the converged rung-0 model: kinematic single-track + understeer + first-order lag + platform-gated per-segment δ₀. It is the cohort-validated ceiling of that *shape* of model. In the m3.v2 cohort, six of ten agents shipped V1's coefficients to three decimal places; the spread across the cohort was 0.3 percentage points on CTE.

V1's local scores against `data/sim/segments/`:

| platform | yaw RMSE (rad/s) | CTE RMSE (m) | residual character (what V1 still gets wrong) |
|---|---|---|---|
| FORD_F_150_LIGHTNING_MK1 | 0.00566 | 62.2 | closest to noise floor; CTE residual is mild drift |
| FORD_MUSTANG_MACH_E_MK1 | 0.00859 | 98.7 | **worst-fitted**; yaw bias + CTE drift; first-order lag is a band-aid for transient dynamics |
| HYUNDAI_IONIQ_5 | 0.00766 | 69.5 | per-segment δ₀ helps but doesn't close the gap; CTE drift ~−12 m |
| TESLA_MODEL_3 | 0 (no truth) | 0 | V0 passthrough; don't try to fit |
| pooled | 0.00587 | 56.8 | — |

V0 pooled for reference: yaw 0.01293, CTE 163.83.

**Your job in m3.v3 is to build candidate models that attack V1's residual structurally, not to refit V1.** A model that imports `code.v1_baseline.predict_v1` and only re-fits its coefficients will score ≈V1 and the preflight will flag it.

## Operating contract — what your `predict()` will see at grading time

The canonical grader hands your `predict(sim_df, platform)` a DataFrame containing **only these eight input columns**:

| column | meaning |
|---|---|
| `t_s` | sample time (s) |
| `delta_wheel_deg` | hand-wheel angle (deg) |
| `delta_road_rad` | road-wheel angle (rad) — the steering channel to use in physics models |
| `v_mps` | vehicle speed (m/s) |
| `a_long_mps2` | longitudinal acceleration (m/s²) |
| `accel_pedal_pct` | accelerator pedal position (%) |
| `brake_pressed` | brake-pressed flag (0/1) |
| `yaw_rate_pred_rads` | V0 baseline yaw rate (rad/s) — V1 uses this as a straight-row gate; you can too |

**Anything else will raise `KeyError`.** Notable absences:

- **`yaw_rate_meas_rads`** — the truth channel. Denied because it's what the grader scores against.
- **`a_lat_meas_mps2`** — lateral acceleration. Denied because in this dataset it's computed kinematically from truth yaw rate (`a_lat = v · ψ̇_truth`), so using it is equivalent to peeking at truth up to a `v` factor. **Some recipes online use `a_lat_meas` as a straight-row gate. Always substitute an allowlist proxy** (e.g. `v_mps * yaw_rate_pred_rads`, `|yaw_rate_pred_rads|`, or `|delta_road_rad|`).
- **`yaw_rate_resid_rads`, `a_y_resid_mps2`, `x_m`, `y_m`, `psi_rad`** — denied (direct or integrated truth leaks).

The local `data/` tree contains TWO views of the same segments:
- **`data/sim-only/segments/`** — agent-facing view. Only the 8 allowlist columns. The local `score-model` skill and `pre-flighting-final-model` use this — local numbers match the canonical grader.
- **`data/sim/segments/`** — full-fidelity view including truth. Useful for *offline* fitting. Anything your `predict()` reads from this set will silently break at grading time.

The Tesla platform has no `yaw_rate_meas_rads` channel (no truth) — V0 passthrough is the honest fallback. Don't fit Tesla.

## Working directory layout

- `code/v1_baseline.py` — the V1 baseline + its fitted coefficients. Import and use; don't edit.
- `code/ks_model.py`, `code/parameters.py` — V0 source and openpilot carParams (mass, inertia, wheelbase priors). carParams are calibrated for upstream use, not ground truth for this data — treat as initial guesses.
- `models/` — one subdirectory per candidate model you build. See § "Models as first-class objects".
- `MODELS.md` — registry of every candidate model: shape, status, dev-score vs V1, verdict.
- `EXPERIMENTS.md` — append-only log of attempts; one entry per concrete attempt.
- `skills/` — toolkit. Inspect each `SKILL.md` metadata before loading the body.
- `references/` — short domain-knowledge docs.
- `_shared/` — local helpers used by skills (trajectory integration, CTE math). Plain Python; modify freely.
- `data/` — symlinked sim data (read-only).
- `final-model/` — where you ship your chosen model. Deliverable contract enforced by `skills/pre-flight-final-model/`.

## Models as first-class objects

Past cohorts treated their work as "one growing `predict.py`". m3.v3 makes models *first-class*: each candidate lives in its own directory, with its own notes, its own assessment, and an entry in a registry. This makes structural comparison cheap, rollback obvious, and accidental convergence on a single model hard.

A candidate model lives under `models/<name>/`:

```
models/
  <model-name>/
    predict.py          # predict(sim_df, platform) -> DataFrame
    notes.md            # formulation, state-space, integrator, priors, expected residual character
    assessment.md       # populated by assess-candidate-model: per-platform vs V1, residual diagnosis, verdict
    <coeffs / helpers>  # anything predict.py depends on
```

Each candidate must:
- Have a `notes.md` describing the **formulation** (equations or pseudo-code), the **state-space** (what's a state, what's an input, initial conditions), the **integrator** (if applicable), and the **expected residual character** — i.e. *which* of V1's residuals you're attacking and why this shape attacks it.
- Be scored alongside V1 using `score-model` and `compare-models`. Save results + conclusions to `assessment.md`.
- Be registered in `MODELS.md`.

The `assess-candidate-model` skill runs the standard battery (score, residual-structure, compare-against-V1) and stamps a populated `assessment.md`. Adapt or replace it per model class if the standard battery isn't the right diagnostic for your model shape — that's the point of having skills be modifiable. A rung-1 dynamic single-track wants a slip-angle diagnostic; a residual learner wants feature-importance; build the diagnostic that's right for *your* model.

Your shipped `final-model/predict.py` is whichever candidate you choose to ship. Often a thin re-export of a `models/<name>/predict.py`. If all your candidates lose to V1 on dev, ship V1 and document the negative result in REPORT.md — that is itself a useful cohort contribution.

## Skills inventory

Inherited from m3.v2 (unchanged):

- `score-model/` — schema-aware scorer for any `predict()` across all platforms. Pooled + per-segment + per-platform signed bias + distribution stats. Always pair with comparing against V1.
- `fit-model/` — per-platform coefficient fitter against yaw / CTE / yaw+CTE. Pass a `predict_factory(platform, coeffs)`; returns fitted coeffs + post-fit diagnostics (co-collapse, stuck-on-bound, overfit-gap).
- `compare-models/` — per-segment diff between two `predict()` functions. **Use this to compare every candidate against V1.**
- `inspect-residuals/` — plot yaw residual vs one or two input features. Useful for spotting *which* feature still drives residual.
- `residual-structure/` — diagnose what's left in the residual: autocorrelation, feature-correlation, sign asymmetry. Returns a verdict (`"noise_floor"` → done with this model; `"structure_detected"` → specific reason).
- `route-bias/` — per-route signed yaw bias and CTE drift ranked by share of platform pooled error.
- `visualise-segment/` — multi-panel PNG of one segment with truth + predictions overlaid.
- `make-train-dev-split/` — route-grouped train/dev split with leakage validator.
- `load-segments/` — load segment `sim.csv`s with consistent dtype hygiene.
- `pre-flight-final-model/` — deliverable-bundle validator. See § "Preflight gates" below.

New in m3.v3:

- `assess-candidate-model/` — coordinator that runs score + compare-vs-V1 + residual-structure on a candidate's `predict.py` and writes a populated `assessment.md` in `models/<name>/`. Treat its output as a starting template — extend with model-class-specific diagnostics.

## References inventory

Read the frontmatter (description + when-to-load) before loading the body.

- `references/exploration-discipline.md` — protocol for naming ≥5 alternatives across model structures before committing. The first thing to load.
- `references/anti-patterns.md` — known traps. Truth peeks, sample-level leakage, denied-column slips. No longer contains a winning recipe — V1 covers that case.
- `references/dynamics-formulations.md` — catalogue of vehicle lateral-dynamics models in increasing structural complexity. V0 documented in full; rungs 1–3 sketched (equations + parameter list + identifiability notes — **no drop-in scaffold**). **Append your shipped formulation here for the next agent.**
- `references/two-kpi-tradeoff.md` — how yaw RMSE and CTE relate. Useful when interpreting your model's numbers.

The references are knowledge, not prescription. If a reference says something you find misleading, edit it. If a reference is in your way, delete it. The only obligation is to lower the canonical KPIs.

## V1's residual diagnosis — what's actually left to attack

V1 leaves three distinct kinds of residual on the data. Each suggests different structural attacks. Pick what to attack based on *your own* residual diagnosis, not from this list — these are pointers, not prescriptions.

1. **Transient-regime yaw error on Mach-E** (yaw RMSE 0.0086, ~2× Lightning). The first-order lag with τ ≈ 0.07 s is a single-pole approximation of dynamics V1 doesn't actually model. Candidate structural attacks: dynamic single-track ODE (rung 1 — see `dynamics-formulations.md`), regime-switched model (V1 for straight, dynamic for transient), residual learner trained on the V1 residual with `d(delta)/dt` and `v_mps` features.

2. **Per-platform CTE drift that survives V1** (Lightning +20 m, IONIQ-5 −12 m residual). V1's δ₀ correction landed the bulk but a tail remains. Candidate structural attacks: complementary filter blending V1 yaw with a steering-derivative-driven signal; per-route bias model fit on input features only; an integrator-error correction (CTE accumulates yaw error linearly with distance — small persistent yaw bias = large CTE).

3. **High-`|a_lat|` segments where V1's linear understeer saturates.** Real tyres saturate. Use the allowlist proxy `|v_mps · yaw_rate_pred_rads| > 4` to find these segments. Candidate structural attacks: nonlinear tyre on top of rung 1 (rung 2), or a piecewise-saturated correction added to V1.

Use `residual-structure/` and `inspect-residuals/` to see which kind dominates *your* model's residual after each iteration. The diagnosis is the work — different residuals point at different structures.

## Preflight gates — what `pre-flighting-final-model` enforces

In addition to the m3.v2 checks (file presence, manifest sanity, allowlist compliance, runs on every declared platform), m3.v3 preflight also enforces:

1. **`MODELS.md` exists with ≥3 candidate entries.** At least one must be tagged `structure: differs-from-V1`. This forces you to *build* multiple candidates instead of fixating on one.
2. **`EXPERIMENTS.md` opens with a ≥5-alternatives header block** (heading "Alternatives considered"). One line per alternative, with model structure named. Three of the five must be structurally distinct from V1. Lifts directly from `exploration-discipline.md`.
3. **Structural-novelty diff against V1.** If your shipped `final-model/predict.py` produces results substantively identical to V1 across the dev set (per-segment yaw difference below a tolerance), preflight warns. You can ship V1 anyway if all your candidates lost — but the warning forces the explicit choice and `REPORT.md` must document the negative result.

The shipped model does **not** need to beat V1. The cohort wants evidence about which structures lose, why, and which (if any) win. A clean negative result is a contribution.

## Inner loop — a workable rhythm

This is a recipe, not a rule. Adapt freely.

1. **Score V1** with `score-model` to confirm the floor and read the per-platform residual breakdown.
2. **Diagnose V1's residual** with `residual-structure` and `inspect-residuals` — find which of the three residual kinds dominates on each platform. This is the start of *your* problem definition.
3. **Open `EXPERIMENTS.md` and write the ≥5-alternatives header** (see `references/exploration-discipline.md`). Three must be structurally distinct from V1. Make the alternatives match the residual you saw in step 2.
4. **Pick the most promising candidate**; create `models/<name>/` with `notes.md` *before* writing `predict.py`. Formulation first, code second.
5. **Build `predict.py`**; score against V1; run `assess-candidate-model` to populate `assessment.md`; register in `MODELS.md`. Write up what the residual structure tells you about whether the model is over- or under-parameterised.
6. **If it lost to V1**, write down *why* in `assessment.md` (under-parameterised? over-parameterised? wrong residual attacked? integrator unstable?), then return to step 3 and pick another alternative. Don't fall back to V1 just to ship — the cohort gets no signal from that.
7. **When you've built ≥3 candidates** with completed assessments, decide what to ship. The candidate that beats V1 on dev pooled metrics is the default ship; if none does, ship V1 with a REPORT.md that names the three structures you ruled out.
8. **Run `pre-flighting-final-model`** and confirm every check passes.

## Working with skills and references

The skills are deliberately small. Treat them as **clay, not library**. The workflow when a skill's output isn't useful:

1. Look at the output. Is the signal you need *in there* somewhere? If yes — extract it inline.
2. If no — the skill is wrong for your model class. Open it, add the diagnostic you need, save, re-run. Per-model-class assessment is expected; that's why the standard battery is a starting point.

Same for references — edit, extend, delete. Only obligation is to lower the canonical KPIs.

## Before declaring done — deliverable hygiene checklist

1. `pre-flighting-final-model` passes every check.
2. `MODELS.md` is consistent with directories under `models/` (no orphan entries, no models without an entry).
3. Every `models/<name>/` has both `notes.md` and `assessment.md`. Skim each `assessment.md` — does it state a verdict and reason?
4. `REPORT.md` (in the agent root) summarises the residual diagnosis you started with, the structures you tried, the verdict on each, and what your shipped model does differently from V1.
5. Read your manifest's `platform_support` out loud. Every declared platform must have a working `predict.py` code path. If you support IONIQ-5 but your coefficients only cover Mach-E and Lightning, IONIQ-5 will silently fall through to V0 — you ship +0% on a third of the pool.

If any check fails, fix and re-run.
