# Implement notes — 20260527-155834

## What ran

`tools/eval_lateral.py` loaded all 315 Mach-E sim CSVs (913,626 samples at
50 Hz), computed the three regime masks once, and evaluated V0–V3 in the
locked order. Output: `out/lateral_eval.json`.

## Sign sanity

`corr(delta_road_rad, yaw_rate_meas_rads)` on cornering = **+0.702** — positive,
ISO 8855 convention intact. No adapter sign flip.

## Results

| variant | all | straight | steady | transient | Δ all |
|---|---|---|---|---|---|
| V0 baseline       | 0.01613 | 0.00877 | 0.03172 | 0.05689 | — |
| V1 seg-bias       | 0.01469 | 0.00493 | 0.03167 | 0.05739 | −0.00143 |
| V2 ST prior C_α   | 0.01551 | 0.00339 | 0.03429 | 0.06287 | **+0.00082 (regression)** |
| V3 ST fit C_α     | 0.01515 | 0.00411 | 0.03308 | 0.06082 | −0.00036 |

Total V0→V3 drop on all-regime RMSE: **−0.00098 rad/s** (≈ 6 %).
Sum of marginals: −0.00097 → within 0.001 of total, well within 15 %
accounting tolerance.

## Deviations from plan

- Plan said V1 bias should propagate into V2/V3. Initial implementation
  carried the **KS-residual** bias into the ST predictor, which is the wrong
  correction (the offset terms are model-specific). Switched to **refitting
  the per-segment straight-line bias against the new predictor** at every
  ladder rung. This is still "one DoF per segment" — same accounting — but
  applied honestly to each model's residual. Noted here rather than rewriting
  the plan.
- V3 optimizer initially returned exactly the prior `(286_551, 355_912)` — the
  L-BFGS-B gradient was below tolerance at parameter scale ~3e5 with loss
  ~1e-3. Rescaled parameters to O(1) (divide by 1e5), tightened `ftol/gtol`,
  and ran from five start points. Converged to **C_αf ≈ 187 584 N/rad,
  C_αr ≈ 154 703 N/rad**. Neither bound pegged.

## Regression flag (V2)

The linear-ST steady-state gain with **openpilot prior C_α** is *worse* than
KS on every cornering bucket on this dataset:

- steady RMSE: 0.03167 → 0.03429 (+8 %)
- transient RMSE: 0.05739 → 0.06287 (+10 %)

Straight-line RMSE improves only because V2 re-estimates per-segment bias
against the new predictor (it has more bias to absorb). The physical reading
is: openpilot's canonical `C_α` for the Mach-E understeers the model by
*more* than KS does on these segments. The form is plausible; the calibration
is wrong for these tyres/roads.

V3 partly recovers this loss by fitting `C_α`. The fitted stiffnesses are
markedly lower than the priors (C_αf 65 % of prior, C_αr 43 % of prior),
which is physically reasonable — they're a tyre that slips earlier than the
openpilot prior assumed. Cornering RMSE recovers most of the V2 regression
but does not beat **V1** (steady: 0.03308 vs 0.03167).

## Headline

On this data, the cheap fix wins: **per-segment straight-line bias removal
(V1) accounts for ~146 % of the eventual V0→V3 drop**, because climbing to
linear-ST (V2) is a net regression and V3 only partially recovers. KS plus a
per-segment offset beats prior-C_α ST and is barely beaten by fitted-C_α ST.

## Painful absence

A real tyre model (Pacejka, V4) would let us test whether the linear-ST form
is the wrong shape for the transient regime, where V3 still loses to V1
(0.06082 vs 0.05739). That's out of scope at the 15-min budget.

## Near-miss

V3 with fitted C_α gets within 0.0004 of V1 on all-regime RMSE — almost
indistinguishable from "just remove the offset." That's the real story: at
the priors the team uses, going from KS to linear-ST does not pay rent.
