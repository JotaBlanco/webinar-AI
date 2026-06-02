---
name: assess-candidate-model
description: Run the standard assessment battery against a candidate model in `models/<name>/` and write a populated `assessment.md` next to its `predict.py`. The battery runs `score-model` (pooled + per-platform), `compare-models` against V1 (per-segment delta with regressions/improvements), and `residual-structure` (autocorrelation, feature correlation, sign asymmetry, verdict). Output is a single markdown file that you can extend with model-class-specific diagnostics — slip-angle plots for dynamic single-tracks, feature-importance for residual learners, etc.
when-to-invoke: After you have `models/<name>/predict.py` working and want to know whether the candidate beats V1, and where it does/doesn't. Run after every meaningful change to predict.py.
when-NOT-to-invoke: Before predict.py imports cleanly (it'll fail on import). While iterating on a single model — use `score-model` directly. The batteries inside this skill are slower than running them individually.
inputs: model_dir (str or Path) — `models/<name>/` to assess. Optional: segment_paths to override default scoring scope.
outputs: dict with `pooled`, `per_platform`, `vs_v1`, `residual_structure`, `assessment_path`. Side-effect: writes `assessment.md` in model_dir.
load-cost: ~180 tokens metadata, ~250 tokens body.
---

# assess-candidate-model

## What it does

`assess(model_dir)` runs:

1. **Score the candidate** with `score-model` (pooled yaw RMSE, pooled CTE RMSE, per-platform breakdown, per-platform signed bias, regime breakdown).
2. **Compare against V1** with `compare-models` (per-segment delta in yaw and CTE between the candidate and V1, top regressions, top improvements, per-platform summary).
3. **Diagnose remaining residual structure** with `residual-structure` (autocorrelation at multiple lags, correlation with allowlist features and their derivatives, sign asymmetry — per platform, with a `verdict` of `noise_floor` or `structure_detected` plus reason).
4. **Write a populated `assessment.md`** next to the candidate's `predict.py`.

The candidate must be importable as `predict(sim_df, platform) -> DataFrame` from `<model_dir>/predict.py`. The skill imports it via `importlib`.

## What the assessment.md contains

A populated markdown file with:

- Headline: pooled yaw / CTE vs V1, with Δ%.
- Per-platform table: yaw + CTE for candidate, for V1, with Δ and sign.
- Per-segment top regressions and top improvements (5 each).
- Residual-structure verdict per platform: `noise_floor` (no more structure to chase) or `structure_detected` with the specific feature/lag the residual still correlates with.
- A `## Verdict` section pre-stubbed for the agent to fill in: keep / shelve, why, what to try next.

The agent is expected to extend the file with model-class-specific diagnostics. Examples:

- **Dynamic single-track**: append a slip-angle scatter, a check of integrator stability across `v_mps` range, identifiability diagnostics for `C_αf` vs `C_αr`.
- **Residual learner**: append feature-importance and cross-platform generalisation.
- **Regime-switched**: append per-regime score breakdown and the switch-threshold sensitivity.

## Usage

```python
from skills.assess_candidate_model.assess import assess

result = assess("models/dynamic-single-track")
print(result["pooled"]["yaw_rate_rmse"], "vs V1:", result["vs_v1"]["delta_yaw_pct"])
# assessment.md is written to models/dynamic-single-track/assessment.md
```

## What it does not do

- Doesn't fit coefficients (use `fit-model`).
- Doesn't decide what to ship (that's a human/agent judgement after reading the assessments of all candidates).
- Doesn't *rank* candidates against each other — for that, read `MODELS.md` or run `compare-models` between two candidates directly.

## Smoke test

`python3 _smoke.py` from this directory. Builds a stub model in a tmp dir, runs `assess`, asserts the assessment.md exists and contains the expected sections.

## Extending this skill

The standard battery is a starting point. If your model class needs different diagnostics, edit `assess.py` (it's ~120 lines) or write a new skill alongside it. Per-model-class assessment is the norm, not the exception.
