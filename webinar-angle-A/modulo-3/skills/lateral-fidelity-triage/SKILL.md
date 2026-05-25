---
name: lateral-fidelity-triage
description: Measure the lateral fidelity gap of the KS vehicle model (predicted ψ̇ vs measured ψ̇) on Ford openpilot segments, decompose it by maneuver regime, and *attribute* the residual to a sequence of incremental model upgrades. Load this when the task asks for lateral RMSE, residual decomposition, or quantifying the contribution of a model change. Not for Tesla data (no truth channel).
when-to-invoke: User asks to compute or improve lateral fidelity, quantify the contribution of a model upgrade, attribute yaw-rate residuals, or compare KS vs ST predictions against Ford-truth data.
load-cost: ~120 tokens metadata, ~900 tokens body.
---

# lateral-fidelity-triage

## Scope

KS-predicted yaw rate (`yaw_rate_pred_rads`) vs Ford-measured yaw rate (`yaw_rate_meas_rads`) at 50 Hz, on the Ford segments under `data/sim/segments/FORD_*/`. Speed-known lateral-only contract: do **not** unclamp `v` or `δ`. The residual you analyse is the lateral model lie.

Lateral acceleration `a_y` is a secondary diagnostic; the headline metric is RMSE of `ψ̇`.

## Procedure (the engineer's walk)

### 1. Pick segments

- Enumerate every `data/sim/segments/FORD_MUSTANG_MACH_E_MK1/**/sim.csv` and every `data/sim/segments/FORD_F_150_LIGHTNING_MK1/**/sim.csv`.
- Use **all four** Ford segments. List them in the report so the run is reproducible.
- Per segment, drop the first and last 1 s of samples (transient artefacts of the integrator initial condition and segment trim).

### 2. Regime segmentation

Define three regimes from the **measured** signals (never from the predicted ones — segmenting on the prediction biases the breakdown):

- `straight` — `|yaw_rate_meas_rads| < 0.05 rad/s` for ≥ 1 s continuously (≈ 50 samples).
- `transient` — `|d(yaw_rate_meas_rads)/dt| > 0.3 rad/s²` (steering input or release), regardless of magnitude.
- `steady-state cornering` — everything else (the residual of `straight` and `transient`).

State the thresholds and the rationale in the report. Sample counts per regime should be reported alongside RMSE so the reader knows where the metric is dense.

### 3. Baseline RMSE table

For each variant (including the baseline), compute RMSE of the residual `pred - meas` overall and per regime:

```
RMSE = sqrt(mean( (yaw_rate_pred - yaw_rate_meas)**2 ))
```

For the **baseline** (existing KS), the residual is already in `yaw_rate_resid_rads` — no need to re-run the simulator, just read the CSV.

### 4. Build the variant ladder

Use the catalogue in `../../references/ks-vs-st.md` to pick the *ordered* sequence of upgrades. The canonical ladder is:

- **V0 — KS baseline** (existing `yaw_rate_pred_rads` column, no work needed).
- **V1 — Parameter recalibration.** Re-fit `L` and `i_s` against the data by minimising RMSE in `straight` + `steady-state` regimes (where KS is structurally near-exact and any miss is parameter bias). Do **not** touch `C_α` here — KS has no C_α. Re-run KS with the fitted parameters.
- **V2 — KS → ST (linear single-track with slip angles).** Use the ST parameters already in `parameters.py` (`m, I_z, l_f, l_r, C_alpha_f, C_alpha_r`). Implement the linear ST yaw-rate equation explicitly (see `references/ks-vs-st.md` for the form). Same speed-known lateral-only contract.
- **V3 — `C_α` tuning by residual minimisation.** Hold ST structure fixed; fit `(C_alpha_f, C_alpha_r)` against the V2 residual on the same segments. Report the fitted values.
- **V4 — Residual ML (optional).** Fit a small linear regressor (or thin MLP) from `(v, δ, |a_y_meas|, δ̇)` to the V3 residual. Train on three segments, evaluate on the fourth (or use k-fold across the four). If you cannot ship this cleanly in your time budget, *omit it and say so in the report* — partial ladders are honest; faked ones are not.

For V1, V2, V3 you must implement and run. V4 is optional but if included must follow held-out evaluation.

### 5. Attribution table

One row per variant. Columns:

```
variant | RMSE_overall | RMSE_straight | RMSE_steady | RMSE_transient | Δ_overall_vs_prev | pct_variance_closed
```

`pct_variance_closed = 100 * (1 - var(resid_this) / var(resid_baseline))`. Negative values are allowed and meaningful (an upgrade can make things worse on a regime).

### 6. Figure

Pick the segment with the highest `std(yaw_rate_meas_rads)` (most transient content). Overlay measured `ψ̇` and the predicted `ψ̇` of every variant. Save as `report.png` in the module root.

### 7. Narrative

≤ 200 words. Name a single most-impactful addition and ground the *why* in the physics it plugs — pull the explanation from `references/ks-vs-st.md` if useful.

## Output contract

`report.md` at the module root with sections in this order:

1. Segment list (4 paths + sample count after trimming).
2. Regime thresholds + sample count per regime.
3. The attribution table (markdown table, units stated).
4. Figure reference (`![](report.png)`).
5. Narrative (≤ 200 words, physics-grounded).

## What this skill explicitly does NOT do

- Does not touch the longitudinal channel. Speed-known is the scope.
- Does not use Tesla. No truth channel.
- Does not invent new model classes (DBM, MB) — those are out of the catalogue.
- Does not re-run rlog → CSV adaptation. The Ford `sim.csv` files already contain everything needed to compute the baseline.
