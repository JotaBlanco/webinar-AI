# Module-4 / agent-05 (angle-C) — Lateral-fidelity challenge

## Headline

KS lateral predictions improved on both Ford platforms via an additive monotone ladder fit per-platform on an interleaved 5th-sample test split. **The dominant model-improvement DOF is a per-platform steering-gain scale `k`, and it has opposite signs on the two platforms** — Mach-E wants k=1.095 (KS under-predicts), F-150 Lightning wants k=0.867 (KS over-predicts). Per-segment bias is reported separately and labelled calibration, not model improvement.

Platforms: FORD_MUSTANG_MACH_E_MK1 (315 segments / 913 626 samples), FORD_F_150_LIGHTNING_MK1 (230 / 667 141). Truth = `yaw_rate_meas_rads`, `a_lat_meas_mps2` (Ford only). Operating contract: KS lateral-only, `v` and `δ` clamped, only ψ, ψ̇, a_y, x, y predicted. Score column: ψ̇ residual recomputed as `pred − meas`.

## Variants (interleaved split, additive, locked order, per-platform fit)

**Mach-E:**

| Variant | DOF | Overall | Straight | Steady | Transient | Marg Δ |
|---|---|---|---|---|---|---|
| V0 baseline | 0 | 0.01613 | 0.00878 | 0.03147 | 0.05743 | — |
| V1 bias (b=+0.00023) | 1 plat | 0.01613 | 0.00876 | 0.03149 | 0.05745 | -0.00000 |
| V2 gain (k=1.0948) | 1 plat | 0.01566 | 0.00979* | 0.02968 | 0.05022 | -0.00047 |
| V3 lag (n=3, 60 ms) | 1 plat | 0.01541 | 0.00967 | 0.02966 | 0.04785 | -0.00025 |
| V4 per-seg bias (cal) | ~315 seg | 0.01323 | 0.00646 | 0.02797 | 0.04483 | -0.00219 |

**F-150 Lightning:**

| Variant | DOF | Overall | Straight | Steady | Transient | Marg Δ |
|---|---|---|---|---|---|---|
| V0 baseline | 0 | 0.02037 | 0.00899 | 0.03629 | 0.05161 | — |
| V1 bias (b=+0.00363) | 1 plat | 0.02005 | 0.00800 | 0.03629 | 0.05158 | -0.00033 |
| V2 gain (k=0.8672) | 1 plat | 0.01637 | 0.00645 | 0.02866 | 0.04474 | -0.00368 |
| V3 lag (n=3, 60 ms) | 1 plat | 0.01614 | 0.00631 | 0.02863 | 0.04336 | -0.00023 |
| V4 per-seg bias (cal) | ~230 seg | 0.01488 | 0.00598 | 0.02647 | 0.03940 | -0.00126 |

Attribution coherence = 0.0000 on both. `*` Regression: Mach-E V2 raises straight RMSE 0.00878→0.00979 — gain >1 amplifies near-zero straight noise; net overall still a win; kept in ladder per `ablation-study` discipline.

## Painful absence

`evals/schema_check.py` **FAILS** on the canonical baseline CSVs (`max diff 1.32e-01`): the stored `yaw_rate_resid_rads` is `meas − pred`, not `pred − meas` as ratchet item #1 declares. RMSE-blind so V0 numbers are unaffected, but any signed downstream analytic would silently invert. **This is exactly the ratchet-#1 past failure sitting in the production data.** My ladder bypasses by recomputing residual from `pred − meas`; producer (`code/generate_simdata_ford.py`) needs fixing.

## Near-misses

- V1 bias on Mach-E ≈ noise (+0.00023). No constant zero-offset on that platform. F-150 has a real +0.00363 (truck IMU thermal offset is the likely physical cause).
- V3 lag scan independently picked n=3 (60 ms) on **both** platforms from [0,10]-sample range — consistent with openpilot CAN latency + small tyre relaxation.

## Surprise

Gain sign flips between platforms. Same kinematic model, opposite mismatches: Lightning's higher mass + longer wheelbase + truck tyres heavily slip-damp ψ̇ vs the kinematic prior; lighter Mach-E with stiffer setup exceeds kinematic ψ̇ via tyre phase-lead and a slight steer-ratio under-statement. **A single fleet-wide multiplicative correction would be the wrong shape of fix — `k` must be per-platform.**

## RPI artifact paths

- `rpi/runs/20260527-160006/research.md`
- `rpi/runs/20260527-160006/plan.md`
- `rpi/runs/20260527-160006/implement-notes.md`
- `out/variant_table_FORD_MUSTANG_MACH_E_MK1.csv`
- `out/variant_table_FORD_F_150_LIGHTNING_MK1.csv`
- `tools/run_ladder.py`

## Eval status

- `evals/baseline_rmse.py`: PASS, V0 matches exactly.
- `evals/schema_check.py`: **FAIL** on baseline CSVs — sign-convention bug in the producer.

## Skills used / authored

Used: `baseline-residual` (V0), `ablation-study` (procedure: interleaved split, additive monotone variants, marginal accounting, per-regime breakdown, regression flagging, coherence check).
**Authored:** `skills/sign-convention-audit/SKILL.md` — distinguishes stored `pred-meas` vs `meas-pred` within 1e-6, so future runs catch the producer bug before any signed downstream stat is trusted.
