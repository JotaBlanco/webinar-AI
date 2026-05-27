# Phase 2 — Plan (LOCKED)

## 1. Selected improvements

**Pick A: H1 — per-segment yaw-rate sensor bias correction.**
*Rationale.* Research showed straight-line `psi_dot_resid` mean is large and
**segment-specific** (+0.70 / -0.09 on Mach-E; -1.49 / -0.53 on F-150). On
Mach-E the model is correct (~0) over the whole segment, so essentially the
ENTIRE 0.505 deg/s RMSE is sensor zero-offset that the residual is paying for.
Removing it should drop Mach-E RMSE by >50% with ~20 LOC. Negligible risk —
purely subtracts a per-segment constant from the *measured* channel during
residual computation.

**Pick B: H3 — analytic understeer-gradient correction.**
*Rationale.* F-150 turn-gain meas/pred = 0.851 (KS over-predicts yaw rate by
~15% under cornering), and residual scales with both v and |a_y| — the
unmistakable signature of tyre compliance. H2 (full ST) would be the proper
fix but is ~120 LOC + integrator stability risk inside a 30-min budget. H3
captures the steady-state portion of ST's correction with a single closed-form
factor: `psi_dot_corrected = psi_dot_KS / (1 + K_u * v^2)` with
`K_u = (m / L^2) * (l_r/C_alpha_f - l_f/C_alpha_r)` computed from the
already-present `MachEST`/`F150LightningST` parameters. Expected ~50-70% of
the high-G residual; cost ~15 LOC.

H1 and H3 are **orthogonal** (bias offset vs gain droop) so their effects
should compose roughly additively in the ablation.

## 2. Implementation steps

1. **New file `tools/lateral_corrections.py`** (under module, not in `code/`
   — keep `code/` clean). Contains:
   - `estimate_yaw_bias(yaw_meas_rads, delta_road_rad, v_mps, ...)` — returns
     scalar bias estimated from samples with `|delta_road|<0.005 rad` AND
     `|yaw_meas|<0.02 rad/s` AND `v>3 m/s`. Use `np.median` (robust).
     If <50 samples qualify, return 0.0 and emit a warning.
   - `understeer_gradient(p_st)` — returns `K_u = (m/L^2)*(l_r/C_af - l_f/C_ar)`.
   - `apply_understeer_correction(psi_dot_ks, v_mps, K_u)` — returns
     `psi_dot_ks / (1 + K_u * v_mps**2)`.

2. **New driver script `tools/regenerate_with_corrections.py`.** Mirrors
   `code/generate_simdata_ford.py` structure but writes to
   `out/sim/segments/<PLATFORM>/<seg>/sim_<variant>.csv` under this module
   (the shared `data/sim/` baseline is read-only — do NOT touch `sim.csv`
   there). Variants:
   - `sim_baseline.csv` — re-run baseline (sanity, should match `sim.csv`).
   - `sim_h1.csv` — apply yaw-bias correction to `psi_dot_pred` (subtract
     `b_hat` from `psi_dot_meas` equivalently → adjust `psi_dot_resid` and
     also `a_y_resid` via `delta_ay = b_hat * v`).
     Equivalent and cleaner: subtract `b_hat` from measured channel before
     computing resid. We'll subtract from measured (consistent with H1 framing
     as "the sensor is biased").
   - `sim_h3.csv` — apply understeer correction to `psi_dot_pred` and
     `a_y_pred = v * psi_dot_pred_corrected`.
   - `sim_h1_h3.csv` — both.
   For each variant, re-derive `yaw_rate_resid_rads` and `a_y_resid_mps2`.
   Read existing baseline `sim.csv` rather than re-decoding rlogs (avoids
   needing CAN-decode deps; columns we need are already in CSV).

3. **New evaluator `tools/eval_ablation.py`.** Reads each variant CSV per
   segment, aggregates per platform, prints a table:
   ```
   variant         | platform | RMSE psi_dot (deg/s) | RMSE a_y (m/s^2) | delta_abs | delta_pct
   ```
   Same metric definitions as Phase-1 baseline so numbers are comparable.

4. **Verify each step.**
   - After step 1: unit-run on a single segment via `python3 -c "..."` smoke.
   - After step 2: assert `sim_baseline.csv` RMSE matches Phase-1 (0.505,
     1.105) within 1e-3.
   - After step 3: confirm H1 alone reduces Mach-E RMSE substantially;
     confirm H3 alone touches F-150 cornering bins.

## 3. Ablation design

Run order, in this exact sequence:

```bash
cd /Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/modulo-4
python3 tools/regenerate_with_corrections.py baseline  # writes sim_baseline.csv
python3 tools/regenerate_with_corrections.py h1        # writes sim_h1.csv
python3 tools/regenerate_with_corrections.py h3        # writes sim_h3.csv
python3 tools/regenerate_with_corrections.py h1_h3     # writes sim_h1_h3.csv
python3 tools/eval_ablation.py                          # final table
```

Ablation rows: baseline → +H1 → +H3 → +H1+H3 (so we can attribute the
incremental gain of each, and the interaction).

## 4. Success criteria

- **Quantitative.**
  - Mach-E RMSE `psi_dot` reduced by >=40% under H1 alone (large bias was
    dominant; this is the smell test).
  - F-150 RMSE `psi_dot` reduced by >=10% under H3 alone (gain term).
  - Combined H1+H3 strictly best (or tied) on both platforms.
  - No platform regresses (>=0% improvement on either metric).
- **Deliverable.** `REPORT.md` at module root containing baseline table,
  proposed-improvements list (>=3 from hypothesis space), implemented changes
  + code paths, ablation table, ranking, and limitations.
