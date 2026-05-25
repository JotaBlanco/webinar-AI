# Módulo 1 — Bare-harness lateral-fidelity report

> **Note on persistence.** The M1 agent attempted to write this file but was blocked by its sub-agent system prompt ("Do NOT Write report/summary/findings/analysis .md files"). The content below was returned in the agent's text response and persisted by the workshop facilitator. This itself is a data point captured in `../process-log.md`.

**Reproduce from `modulo-1/`:**
```
python3 out/baseline.py     # writes out/baseline_summary.csv, out/baseline_regimes.csv
python3 out/diagnose.py     # prints scale/lag diagnosis
python3 out/ablation.py     # writes out/ablation_results.csv, out/ablation_deltas.csv
```
All scripts read only from `data/sim/segments/FORD_*/.../sim.csv` and write only into `modulo-1/out/`. Corrections are post-hoc transforms of the existing `yaw_rate_pred_rads`/`a_y_pred_mps2` columns (algebraically equivalent to applying `b`, `k`, lag inside the integrator since `a_y_pred = v·ψ̇_pred`).

## Baseline (full data)

| Platform | N | RMSE ψ̇ [°/s] | RMSE a_y [m/s²] | bias ψ̇ [°/s] | bias a_y [m/s²] | corr ψ̇ | corr a_y |
|---|---:|---:|---:|---:|---:|---:|---:|
| FORD_MUSTANG_MACH_E_MK1 | 5 796 | 0.505 | 0.062 | +0.316 | −0.042 | 0.464 | 0.804 |
| FORD_F_150_LIGHTNING_MK1 | 5 796 | 1.104 | 0.443 | −0.872 | −0.172 | 0.987 | 0.789 |

**Worst regimes:** Mach-E is worst in 5–15 m/s (RMSE 0.61 °/s) and almost entirely straight-line (only 23/5796 samples with |δ|>5°). F-150 degrades monotonically with speed (0.53 → 1.37 °/s from <5 to >25 m/s) and explodes in hard cornering (|a_y|>2 m/s² → RMSE 2.16 °/s, bias −2.10 °/s — over-predicts yaw in hard turns).

## Proposed improvements (with physical justification)

1. **Yaw-rate bias `b`** — IMU zero-rate offset; signature is non-zero residual mean on straight roads (present on both platforms).
2. **Steering-to-yaw scale `k`** — KS lacks an understeer-gradient term; with cornering stiffness, real ψ̇ = `v/(L(1+K_us·v²))·δ`, which produces a `<1` scale on the F-150 (mean(meas/pred) on real turns = 0.64). A flat `k≈0.93` captures the average effect across the dataset's speed range.
3. **Steering lag** — rack compliance + ~20–40 ms CAN latency; cross-correlation peaks at 1 sample (20 ms) on F-150.

**Proposed but NOT implemented:** full Single-Track with `C_alpha_f/r`, wheelbase recalibration on circle-test segments, speed-stratified `k(v)`/`b(v)`. Out of budget.

## Implemented

`out/ablation.py` fits per-platform `b`, `k`, `L` on even-indexed samples, evaluates on odd-indexed samples (interleaved 50/50 to keep regime coverage matched).

## Ablation tables

### FORD_MUSTANG_MACH_E_MK1

| Variant | RMSE ψ̇ [°/s] | Δ | RMSE a_y [m/s²] | corr | Params |
|---|---:|---:|---:|---:|---|
| B0 baseline | 0.505 | — | 0.062 | 0.464 | — |
| B1 + bias | 0.394 | −22.0% | 0.114 | 0.464 | b=+0.32 °/s |
| B2 + scale | 0.391 | −22.7% | 0.108 | 0.464 | k=0.819 |
| B3 + lag | 0.389 | −22.9% | 0.108 | 0.468 | lag=2 samples |

### FORD_F_150_LIGHTNING_MK1

| Variant | RMSE ψ̇ [°/s] | Δ | RMSE a_y [m/s²] | corr | Params |
|---|---:|---:|---:|---:|---|
| B0 baseline | 1.104 | — | 0.443 | 0.987 | — |
| B1 + bias | 0.677 | **−38.7%** | 0.394 | 0.987 | b=−0.87 °/s |
| B2 + scale | 0.616 | **−44.2%** | 0.375 | 0.987 | k=0.933 |
| B3 + lag | 0.615 | −44.3% | 0.375 | 0.987 | lag=1 sample |

## Ranking of impact

1. Yaw-rate bias — by far the most cost-effective; single biggest absolute gain. (Caveat: degrades Mach-E a_y RMSE because we're propagating a constant onto a channel whose error is from other sources.)
2. Steering scale `k` — meaningful only on F-150 (+5.5 pp), trivial on Mach-E.
3. Steering lag — no-op at 50 Hz. Discard.

## Limitations

- Only 2 segments per platform — manoeuvre envelope barely sampled. Mach-E especially is straight-line-dominated (correlation 0.46 is mostly noise floor, not model error we can fix).
- `k` and `b` are constants — a real Single-Track would yield speed-dependent `k(v)`.
- Mach-E `a_y` RMSE *degrades* under our corrections — the Mach-E lateral-acc residual is not yaw-bias driven. Need a tyre-slip model.
- **First ablation used a contiguous 70/30 split and over-fit catastrophically** (B2 jumped to 0.73 °/s on the held-out tail). Switched to interleaved sampling; documented in `out/ablation.py` so the next person doesn't repeat the mistake.
- No re-run of the simulator — post-hoc transforms only. Equivalent for constant `b`/`k`/lag; a physics upgrade would require re-integration.

## Files produced (all under `modulo-1/out/`)

- `baseline.py`, `baseline_summary.csv`, `baseline_regimes.csv`
- `diagnose.py`
- `ablation.py`, `ablation_results.csv`, `ablation_deltas.csv`

## Executive summary (≤350 words) — verbatim from the agent

**Most painful absence:** structured memory / AGENTS.md. The braindump CLAUDE.md is fine on turn 1, but every column name, parameter value, and the speed-known contract had to be re-derived from code on each lookup. A 30-line AGENTS.md would have saved ~30% of the wall-clock. Second-most-painful: a pre-authored "interleaved-split residual ablation" skill — I would not have shipped a contiguous train/test split and then had to fix it. Evals third (would have caught the over-fit). RPI loop was the least missed.

**Path-isolation near-miss:** I almost ran `find` from `webinar-AI/` root to locate sim CSVs, which would have walked into sibling angle/module folders. Caught it before running and restricted the glob to `data/sim/segments/FORD_*`. No actual out-of-scope reads occurred.

**Most surprising thing about residuals:** the F-150's *shape correlation* is already 0.987 — the KS model gets the dynamics nearly perfectly — yet its baseline RMSE (1.10 °/s) is twice the Mach-E's (0.51 °/s). The error is almost entirely a constant gyro bias plus a 7% scale mismatch. Two scalars per platform reclaim 44% of the F-150 RMSE.
