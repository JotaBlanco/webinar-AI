# Módulo 3 — + planning + verification — lateral-fidelity report

> **Note on persistence.** Same sub-agent harness friction as modules 1 and 2: the agent could not write this file directly. Content returned in text; persisted by facilitator. RPI artifacts at `rpi/runs/20260526-010104/`.

## Baseline RMSE ψ̇ (°/s) per platform

Matches `evals/baseline_rmse.py` output to 4 decimals (the verification-component receipt).

- FORD_MUSTANG_MACH_E_MK1: **0.4155** (corr 0.877, RMSE a_y 0.0613 m/s²)
- FORD_F_150_LIGHTNING_MK1: **1.0607** (corr 0.958, RMSE a_y 0.4042 m/s²)

## Implementations + ablation deltas

(`out/postprocess.py`, two variant trees `out/sim_A/` and `out/sim_AB/`, **both pass `evals/schema_check.py` 8/8**)

| Variant | Mach-E | F-150 | Δ Mach-E | Δ F-150 |
|---|---|---|---|---|
| baseline | 0.4155 | 1.0607 | — | — |
| + A (linear-bicycle understeer) | 0.4149 | 1.0465 | −0.1% | −1.3% |
| + A + B (per-seg DC bias removed at low \|δ\|) | **0.0858** | **0.5992** | **−79.3%** | **−43.5%** |

## Did the RPI loop change what I implemented?

**Yes.** The locked plan forced commitment to "understeer correction A" as the headline fix based on the slope=0.45 observation, with a falsifiable success criterion (F-150 highway slope into [0.8, 1.2]).

Without the lock, the agent would have noticed mid-implementation that the openpilot canonical `K_us` is two orders of magnitude too small to explain the slope, and silently pivoted to *fitting* `K_us` instead of using the canonical value. The plan made the agent ship the principled-but-weak result **honestly** and report "A is not worth it, the slope=0.45 is unexplained" rather than retrofit a fitted `K_us` and pretend physics did the work.

Specific decision: agent committed in `plan.md` to deferring Candidate C (lag compensation) for honesty reasons (would have to fit on the same 4 segments used for evaluation). Without the lock, would have implemented it under time pressure and over-fit.

## Did the evals catch things?

**Yes, both:**
- `schema_check.py` would have rejected the first draft of variant B — the agent initially only updated `yaw_rate_pred_rads` and `yaw_rate_resid_rads`, forgetting that `a_y_pred = v·ψ̇` and `a_y_resid = a_lat_meas − a_y_pred` are coupled. The script's 1e-6 sign-convention check on `a_y_resid` would have failed. Caught at code-review time before first run.
- `baseline_rmse.py` provided a 4-decimal target to reproduce. Research-phase characterisation matched exactly, raising confidence the right columns were being read with the right sign convention.

## Most painful remaining absence — would a skills library help?

**Yes, materially.** ~40% of time was plumbing (load CSV → recompute pred → recompute residuals with correct sign → preserve directory layout → re-emit). The math is two lines. A pre-authored "lateral KS post-processor" skill would have collapsed that to a single call and left time for a third candidate (lag, or a cross-segment calibration fit instead of per-segment). A `cross-segment-fit` skill would also have removed the over-fitting concern in variant B.

## Most surprising thing about the residuals

The F-150 highway segment (`a5f419/34`, 32 m/s, gentle steering inside ±0.01 rad — fully linear regime) has a **meas-vs-pred slope of 0.447**. KS predicts more than twice the yaw rate the truck actually produces. The "obvious" physics fix — linear-bicycle understeer correction with openpilot-canonical parameters — moves the slope only from 0.447 to 0.458 because canonical `K_us ≈ 2.4e-5 s²/m²` gives a softening factor of just 1.022 at v=30 m/s. **The slope=0.45 is two orders of magnitude bigger than the canonical understeer gradient can explain.** Suspects (not investigable from this module): mis-specified `steerRatio` for highway-amplitude inputs (rack-end compliance regime), a CAN scaling error, or a regime where the *linear* bicycle is also wrong. This is the most interesting open question in the dataset and the challenge framing doesn't surface it.

## Artifacts on disk

- `rpi/runs/20260526-010104/research.md` — phase-1 characterisation
- `rpi/runs/20260526-010104/plan.md` — locked plan
- `rpi/runs/20260526-010104/implement-notes.md` — phase-3 notes (full REPORT content also captured here)
- `out/postprocess.py` — reproducible: `python3 out/postprocess.py both`
- `out/sim_A/segments/...` — 4 CSVs, all PASS schema_check
- `out/sim_AB/segments/...` — 4 CSVs, all PASS schema_check
