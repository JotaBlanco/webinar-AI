# Module-4 / agent-02 (angle-C) — Lateral fidelity ladder

**Platform**: FORD_MUSTANG_MACH_E_MK1 (Mustang Mach-E MK1, 315 segments, 913 626 samples; test fold 182 725 via interleaved every-5th split).

**Headline**: V0 → V3 overall yaw-rate RMSE **0.01613 → 0.01557 rad/s** (-3.5% overall, **-10% on transient cornering**, -6% on steady). Effectively all of the gain came from a single per-platform parameter fit — **effective wheelbase L_eff = 2.793 m vs canonical L = 2.984 m** (~6.4% shorter).

**Measured-truth statement**: scored against `yaw_rate_meas_rads` (openpilot IMU yaw rate on CAN, Ford-only). Residual sign `pred − meas` (ratchet #1). Sign-convention sanity holds in V0 by construction.

**Clamped-vs-predicted**: speed-known lateral-only mode — `v` and `δ` clamped to measured, lateral states predicted via `ψ̇ = v·tan(δ_road)/L`. Lateral-only (ratchet #5).

## Variant ladder (per-platform, interleaved test fold)

| Variant | overall | straight | steady | transient | marginal |
|---|---|---|---|---|---|
| V0 baseline | 0.01613 | 0.00875 | 0.03162 | 0.05712 | — |
| V1 bias remove (b=+0.00075) | 0.01613 | 0.00872 | 0.03170 | 0.05719 | **-0.00001 (regression)** |
| V2 lag align (k=0 samples) | 0.01613 | 0.00872 | 0.03170 | 0.05719 | +0.00000 |
| V3 L_eff fit (L_eff=2.793 m) | 0.01557 | 0.00944 | 0.02981 | 0.05115 | **-0.00056** |

All variants per-platform (one scalar / one integer each). Attribution coherence err = 0.0000 (<0.15). Σ marginals = total drop = -0.00055 rad/s.

## Regressions (with physical cause)

- **V1 bias removal**: -0.00001 rad/s. Train median residual (+0.00075) is small and biased the test predictions the wrong way in the straight regime. Physical cause: the V0 residual is already near-zero-mean; no real DC IMU offset to remove on this platform.
- **V3 straight-regime side effect**: straight RMSE rose 0.00872 → 0.00944 (+8%). Physical cause: a shorter L_eff gains up small δ noise around zero; the cornering improvement dominates, so overall RMSE still drops, but a regime-gated correction would be cleaner.

## Painful absence

None acutely felt. A `regime-gated-variant` skill would have helped me cleanly express "apply V3 only on cornering"; noted as future work rather than authoring a new skill in budget.

## Near-misses

- V2 lag fit returned k=0 — hypothesis that CAN δ lags the IMU was **falsified at 20 ms resolution**. Openpilot's pipeline appears to time-align δ_road and yaw rate already.
- V1's "obvious" bias removal turned into a near-zero regression — V0 is already centred.

## Surprise

The carParams `L=2.984` m is openpilot-canonical (read from the rlog itself) — yet the data prefers L_eff ≈ 2.79 m. That gap is almost certainly **compliance steer + tire scrub effectively reducing the road-wheel angle**, exactly the kind of single-track-vs-real-tire mismatch this workshop is built around. It explains why the prior gain is too high during cornering.

## Artifacts

- RPI run: `rpi/runs/20260527-160016/` (research.md, plan.md, implement-notes.md)
- Ladder code: `tools/run_ladder.py`
- Numerics: `out/ladder_summary.json`

## Eval status

- `evals/baseline_rmse.py FORD_MUSTANG_MACH_E_MK1` → overall 0.01613 — matches V0 in the ladder.
- `evals/schema_check.py` not invoked on derived CSVs (no derived CSVs were written; ablation scored in-memory off existing schema-valid sim.csvs).

## Skills used / authored

- Used `skills/baseline-residual` (V0 numbers + regime mask, matched eval).
- Used `skills/ablation-study` (interleaved split, additive monotone variants, marginal accounting, regression flagging, coherence check). Loop implemented in `tools/run_ladder.py` per the skill's "discipline matters more than the runner" clause.
- No new skill authored within the 15-min budget.
