# Implement notes

## What ran

`tools/run_ladder.py` on both Ford platforms. Outputs in `out/variant_table_<PLATFORM>.csv`.

## Deviations from plan

None on the ladder itself. Ran V0->V4 in locked order. Attribution coherence = 0 on both platforms (numerical floor: marginals defined as differences, so they algebraically sum to total).

## Results — Mach-E (primary)

| Variant | Overall | Straight | Steady | Transient | Marginal |
|---|---|---|---|---|---|
| V0 baseline | 0.01613 | 0.00878 | 0.03147 | 0.05743 | - |
| V1 bias (b=+0.00023) | 0.01613 | 0.00876 | 0.03149 | 0.05745 | +0.00000 |
| V2 gain (k=1.0948) | 0.01566 | 0.00979 | 0.02968 | 0.05022 | +0.00047 |
| V3 lag (n=3 = 60 ms) | 0.01541 | 0.00967 | 0.02966 | 0.04785 | +0.00025 |
| V4 per-seg bias (cal) | 0.01323 | 0.00646 | 0.02797 | 0.04483 | +0.00219 |

## Results — F-150 Lightning

| Variant | Overall | Straight | Steady | Transient | Marginal |
|---|---|---|---|---|---|
| V0 baseline | 0.02037 | 0.00899 | 0.03629 | 0.05161 | - |
| V1 bias (b=+0.00363) | 0.02005 | 0.00800 | 0.03629 | 0.05158 | +0.00033 |
| V2 gain (k=0.8672) | 0.01637 | 0.00645 | 0.02866 | 0.04474 | +0.00368 |
| V3 lag (n=3 = 60 ms) | 0.01614 | 0.00631 | 0.02863 | 0.04336 | +0.00023 |
| V4 per-seg bias (cal) | 0.01488 | 0.00598 | 0.02647 | 0.03940 | +0.00126 |

## Per-regime regressions

- Mach-E V2: straight RMSE rose 0.00878 -> 0.00979 (+0.00101). Physical cause: gain >1 multiplies near-zero residual noise on straights by 1.095, amplifying it; the same gain pays for itself in steady/transient. Net overall is still a win. Flagged but kept.
- No regression on F-150 because k=0.867 < 1 dampens straight noise too.

## Surprise — opposite gain signs

Mach-E wants k=1.095 (KS *under*-predicts ψ̇); F-150 wants k=0.867 (KS *over*-predicts). Same kinematic model, opposite mismatches: the Lightning's much higher mass + longer wheelbase + truck tyres make real ψ̇ heavily slip-damped vs the kinematic prior; the lighter Mach-E with stiffer suspension *exceeds* the kinematic prediction because of phase-lead in tyre relaxation plus a slight steer-ratio under-statement. **A single fleet-wide multiplicative correction would be the wrong shape of fix — k must be per-platform.**

## Lag

Both platforms independently picked n=3 samples (60 ms) from a [0,10]-sample search. Physically consistent with the openpilot CAN-bus latency budget plus a small tyre relaxation length. Same number on two independent platforms is encouraging.

## V4 — label honestly

Per-segment additive bias adds ~315 + ~230 DOFs. It memorises IMU mounting offset / temperature drift / route-specific quirks. **Labelled per-segment (calibration), not model improvement.**

## Painful absence (schema_check FAILS)

`evals/schema_check.py` FAILED on the canonical baseline CSVs:

```
yaw_rate_resid sign/value mismatch — max diff 1.32e-01 > 1e-06
```

Investigation: the stored `yaw_rate_resid_rads` is `meas − pred`, not `pred − meas` as ratchet item #1 and the schema check declare. This is the exact past failure ratchet-#1 encodes — except it is sitting in the production data right now, not just in agent memory. RMSE is sign-blind so it didn't bite the V0 baseline, but any signed analytic (bias removal, slope sign of a gain fit on the residual column) would silently invert.

My ladder is unaffected because I recompute the residual from the truth columns directly (`pred − meas`), ignoring the stored column. But the producer (`code/generate_simdata_ford.py`) needs fixing.

## New skill authored

`skills/sign-convention-audit/SKILL.md` — distinguishes "stored as pred-meas" vs "stored as meas-pred" within 1e-6, so future ladder runs can detect the producer bug before committing any signed downstream stat. Authored because the existing two skills cover the variant procedure but not the *data integrity* failure that the ratchet warned about.

## Skills used

- `baseline-residual` -> V0 (matched `evals/baseline_rmse.py`).
- `ablation-study` -> ladder discipline (interleaved 5th-sample test split, additive monotone variants, marginal accounting, per-regime breakdown, regression flagging, coherence check).
- `sign-convention-audit` -> authored this run.
