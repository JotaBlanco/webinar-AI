---
name: ablation-study
description: Disciplined ablation procedure for a vehicle-dynamics variant ladder. Enforces interleaved train/test split (every 5th sample → test), additive monotone variants in fixed order, strict marginal RMSE attribution, per-regime breakdown, regression flagging, and a 15% attribution-coherence sanity check. Use when running the variant ladder.
when-to-load: Whenever you build a variant ladder (V0 → V1 → … → V_last) with attribution.
inputs: A list of variant functions you've implemented; the segment set; the regime mask (from baseline-residual).
outputs: A variant table (rows = variants, columns = overall RMSE + per-regime RMSE + marginal Δ), an attribution-coherence number, a list of regression rows.
load-cost: ~250 tokens metadata, ~700 tokens body.
---

# ablation-study

## When to load

When you have ≥2 candidate variants on top of V0 and want to attribute each variant's contribution honestly. Load before V1 is reported.

## The procedure (fixed, do not deviate)

### 1. Fix the segment set

A single segment list, deterministic order. All variants score on this set. Document the count.

### 2. Fix the regime mask

The same mask `baseline-residual/run.py` uses: straight (`|δ_road| < 0.01`), steady (`|δ_road| ≥ 0.01 ∧ |δ̇| < 0.05`), transient (`|δ_road| ≥ 0.01 ∧ |δ̇| ≥ 0.05`).

### 3. Interleaved train/test split (when fitting)

For any variant that fits a parameter to data, split **every 5th sample → test, remaining 4/5 → train**. Do **not** use a contiguous front/back split — the residual is autocorrelated and a contiguous split over-fits catastrophically. Report the held-out test RMSE, not the train RMSE.

### 4. Additive monotone variants

Each rung V_i adds **one** degree of freedom to V_{i-1}. Variants in a fixed order. Do not change the order mid-run.

### 5. Marginal attribution

Each variant's marginal drop = `RMSE(V_{i-1}) − RMSE(V_i)`. Positive = improvement. Negative = regression (flag it).

### 6. Attribution-coherence check

`|Σ marginal − total|/|total| < 0.15`. If above, you have either double-counting or numerical instability — investigate before shipping.

### 7. Regression flagging

A negative marginal drop is **not silently dropped**. It is reported as a regression row with a **physical cause** (e.g. "openpilot prior C_α stiffer than this car's tyres want").

### 8. Per-segment vs per-platform labelling

State whether each variant fits per-segment or per-platform. A per-segment fit memorises a sensor offset — that is calibration, not model improvement.

## Usage

```bash
python3 skills/ablation-study/run.py <variant-list-script.py>
```

Where `<variant-list-script.py>` exposes a `VARIANTS` list of callables. Each callable takes a DataFrame (the segment set with V_{i-1} applied) and returns the new `yaw_rate_pred_rads`. The runner produces the variant table + attribution-coherence number + regression list.

If you'd rather implement the loop yourself in `tools/`, the discipline in steps 1–8 is what matters. The runner is a reference implementation, not a requirement.

## Discipline

- A variant that worsens RMSE is **not** dropped from the ladder. Drop it from the *shipped* recommendation if you must, but report it.
- The attribution-coherence check is a tripwire. If it fires, your story is wrong.
