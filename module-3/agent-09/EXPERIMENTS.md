# EXPERIMENTS.md

Append-only log of approaches you tried. One entry per concrete attempt. See `references/exploration-discipline.md` for the why.

Schema:

```
## E<NN> — <one-line approach name>
- Hypothesis: why you thought this would help, in one line.
- What I changed vs E<NN-1>: the minimal diff.
- Result (dev): yaw <old> → <new> (Δ%); CTE <old> → <new> (Δ%).
- Verdict: keep | revert | revisit-later.
- Things this rules out: what you learned, even if the experiment failed.
```

Delete this header section once you start logging, but keep the schema close to mind.

---

## E00 — V0 baseline (no changes)
- Hypothesis: establish the floor we're trying to beat.
- What I changed vs nothing: nothing — predict() passes through `yaw_rate_pred_rads`.
- Result (full sim/): yaw 0.01471 rad/s pooled; CTE 163.83 m pooled. Lightning + Ioniq5 both flag big signed yaw bias driving CTE drift (-54.8 m Ioniq5, +39.7 m Lightning).
- Verdict: baseline.
- Things this rules out: nothing yet.

## E01 — Per-platform calibrated kinematic-ST + first-order yaw lag
- Hypothesis: the V0 baseline (`code/ks_model.py`) uses raw `delta_road_rad` / `L`; the bias warnings show steering scale + understeer + lag are uncalibrated. Refs/dynamics-formulations.md documents the calibrated V0 form. Fit `{L_eff, g, delta0, K_us, tau}` per platform via Nelder-Mead on pooled yaw MSE.
- What I changed vs E00: replaced echo-V0 with a fitted steady-state-understeer + first-order-IIR model. Tesla left at identity (no truth channel).
- Result (full sim/): yaw 0.01471 → **0.00627 rad/s** (-57%); CTE 163.83 → **79.45 m** (-51%). Per-platform yaw bias now all under threshold; Ioniq5 still flags cte_drift = -11.6 m (no longer 3x).
- Verdict: keep — shipped as final-model/.
- Things this rules out: most of V0's loss was *miscalibration*, not missing physics. The biggest single mover was the Lightning's `g` ≈ 0.73 (vs unfit ~1.0): suggests Lightning's `delta_road_rad` already had partial steering-ratio scaling applied upstream, and an extra ~27% scale was being double-counted. Similar story in reverse for Mach-E (g≈1.07).
