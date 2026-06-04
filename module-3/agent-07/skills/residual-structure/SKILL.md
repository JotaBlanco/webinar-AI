---
name: residual-structure
description: After a fit, characterise what's LEFT in the residual — temporal autocorrelation at multiple lags, Pearson correlation with each input feature AND its first time-derivative, sign-asymmetry in δ. Returns a per-platform **verdict** — either "noise_floor" (stop; you're done) or "structure_detected" with a specific reason ("residual autocorrelated at lag 6 → try a τ·d(δ)/dt term"). Use as the bridge between fit-model and "is V2 worth building?". This is the diagnostic the v2 cohort silently lacked — almost everyone shipped V1 understeer; the one agent who didn't (m2-agent-05, +51.5% yaw) saw exactly this autocorrelation signature and added a steering-rate lead.
when-to-invoke: After running `fit-model` and `score-model`, when you're trying to decide whether your current model has more headroom or you're at the noise floor. Especially when yaw RMSE has stalled and you don't know whether to ship or keep iterating.
when-NOT-to-invoke: Before any fit (run scoring-model first — you need a fitted predict_fn). To see route-level bias (use route-bias). To plot residual vs one feature (use inspect-residuals).
inputs: predict_fn (callable), segment_paths (default — all platforms), platform_filter, sample_filter_v_mps, features (tuple of column names — default v_mps, delta_road_rad, a_long_mps2, yaw_rate_pred_rads), lags (tuple of ACF lags in samples — default 1, 2, 5, 10, 20).
outputs: dict — per_platform → {n_segments, n_samples, residual_std, acf, feature_correlations (raw AND derivative, sorted by |ρ|), asymmetry, verdict, verdict_reason}, plus failed_segments and lags.
load-cost: ~210 tokens metadata, ~500 tokens body.
---

# residual-structure

## Why this exists

The v2 cohort hit a yaw ceiling at ~+48% because almost everyone fit V1 understeer (`v·δ / (L + K_us·v²)`), saw the per-platform bias collapse, and shipped. The one winner ([m2-agent-05](module-2/agent-05/REPORT.md), +51.5%) did the same V1 first, then noticed the V1 residual was *autocorrelated* and added a steering-rate lead `τ·d(δ)/dt`. The fitted τ converged to **−60 ms** on every platform — a real sensor-pipeline delay that the static understeer model had no way to capture.

The other agents didn't see this because nobody plots ACF of residuals by default. This skill makes that signal cheap.

## What it checks

After running your `predict_fn` over the requested segments and computing per-row residual, the skill pools across segments per platform and runs four checks:

1. **Autocorrelation** at lags 1, 2, 5, 10, 20 samples (configurable). If `|ACF(lag>0)| > 0.10` at any lag, the residual has *memory* — adjacent samples are correlated. That means the model is missing a dynamic / lead-lag term. m2-agent-05's `τ·d(δ)/dt` came from exactly this.
2. **Cross-correlation with each input feature AND its first time-derivative.** If `|ρ(residual, d(δ)/dt)| > 0.10`, you need a derivative term. If `|ρ(residual, v_mps)| > 0.10` after a fit that already has `v` in it, your `v` term has the wrong shape (try `v²` or speed-conditioned gain).
3. **Sign-asymmetry in δ.** Pools the mean residual in `δ > +0.02` vs `δ < -0.02` bands. Odd-component share = `|mean+ − mean−| / (|mean+| + |mean−|)`. If > 0.20, the residual is sign-flipped between left and right turns — try `α3·δ³` (sign-symmetric magnitude term) or a sign-of-δ̇ hysteresis term.
4. **Verdict.** If none of the above fires, the verdict is `noise_floor` — stop, you're done for this model class. If any fires, the verdict is `structure_detected` and the reason names the specific signal and the suggested model term.

## Dashboard

`format_residual_structure_summary(result)` opens with a verdict table per platform — that's the answer. Below it, the supporting detail per platform: ACF table with ⚠️ on lags above threshold, ranked feature-correlations table with ⚠️ on rows above threshold, asymmetry block.

## Usage

```python
from skills.fit_model.fit               import fit
from skills.score_model.score           import score
from skills.residual_structure.residual_structure import (
    residual_structure, format_residual_structure_summary,
)

# 1. Fit your V1 model and build the corresponding predict_fn.
fit_result = fit(predict_factory, init_coeffs, train_segments,
                 objective="cte", dev_segments=dev_segments, bounds=bounds)
predict_fn = lambda sim_df, plat: pd.DataFrame(
    {"yaw_rate_pred_rads": predict_factory(plat, fit_result["coeffs"][plat])(sim_df)},
    index=sim_df.index,
)

# 2. Score, then diagnose what's left.
print(format_residual_structure_summary(residual_structure(predict_fn)))
```

A typical V1 understeer fit on this dataset will show **structure_detected** with autocorrelation at lag ~5–10 samples. That's your prompt to build V2.

## Thresholds

Module-level constants — edit if your noise scale differs:

- `ACF_NOISE_THRESHOLD       = 0.10`
- `XCORR_NOISE_THRESHOLD     = 0.10`
- `ASYMMETRY_NOISE_THRESHOLD = 0.20`

These are deliberately permissive: a residual with |ACF(lag=1)| = 0.10 is *clearly* not white. If you want to ship more aggressively, raise them; if you're hunting for the last 5%, lower them.

## What it does not do

- Does not propose a specific functional form. It says "autocorrelated → try a derivative term"; you pick the form.
- Does not refit. Pair with `fit-model` after you add the new term.
- Does not handle non-stationarity within a segment. It treats each segment as a stationary process and pools across segments. If your residual changes structure mid-segment, use `inspect-residuals` or `visualise-segment` instead.

## Smoke test

`python3 _smoke.py` — V0 passthrough across all platforms. The V0 residual is heavily structured (V0 is the kinematic baseline with no understeer at all), so the verdict for every Ford/Hyundai platform should be `structure_detected`. Tesla's V0 truth IS V0 so the verdict on Tesla should be `noise_floor` (residual is identically zero).

## Extending this skill

- Add a power-spectral whiteness test (FFT of the residual, check the ratio of low- to high-frequency variance).
- Replace Pearson ρ with Spearman to catch non-linear monotone relationships.
- Add a "feature × regime" cross-correlation (`ρ(residual, feature)` split by `straight | steady | transient`) — sometimes structure shows up in one regime only.
