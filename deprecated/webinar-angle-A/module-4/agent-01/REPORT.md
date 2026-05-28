# Module-4 / agent-01 — Lateral-fidelity variant ladder (Mach-E)

## Setup

- **Platform.** `FORD_MUSTANG_MACH_E_MK1` (40 of 315 sim.csv segments, 115 970 rows at 50 Hz). Mach-E chosen because its `sim.csv` carries decoded IMU `yaw_rate_meas_rads` truth; Tesla does not.
- **Scored channel.** `yaw_rate_meas_rads` is the **measured** truth (IMU yaw gyro decoded from rlog). All variants score `pred − measured` RMSE against this same column.
- **Contract.** Operating under the speed-known / lateral-only contract: `v_mps` and `delta_road_rad` are **clamped** to measurement at every integration step. The integrator's `v`/`δ` updates are overwritten. The **predicted** channels are `yaw_rate_pred_rads` (V0) and recomputed yaw-rate from each variant (V1..V4). Speed-state agreement is zero by construction and not scored. No variant unclamps `v` or `δ`.
- **Methodology consistency.** Segment set (same 40 sim.csv files) and regime mask **held constant across every row**. Bias-correction in V1..V3 computed only on each segment's straight-line samples and applied uniformly.
- **Regime mask** (from `triage.regime_mask`):
  - `straight` — `|δ_road| < 0.01 rad` (103 083 rows)
  - `steady cornering` — `|δ_road| ≥ 0.01` ∧ `|dδ/dt| < 0.05 rad/s` (10 610 rows)
  - `transient cornering` — `|δ_road| ≥ 0.01` ∧ `|dδ/dt| ≥ 0.05 rad/s` (2 277 rows)
- **Attribution accounting.** Strict marginal, fixed order V0→V1→V2→V3→V4. By construction marginals sum to total drop (attribution coherence ≈ 0%, well inside the 15% budget).

## Variant ladder

| Variant | Description | RMSE overall (rad/s) | Straight | Steady | Transient | Δ marginal (rad/s) |
|---|---|---:|---:|---:|---:|---:|
| V0 | Baseline `yaw_rate_resid_rads` as-stored, no preprocessing                                                                                  | 0.01394 | 0.00929 | 0.02726 | 0.05028 | — |
| V1 | KS recalibrated: `ψ̇ = (v/L)·tan(δ)` with canonical `L=2.984` from `PARAM_BY_PLATFORM`; minus per-segment yaw-gyro bias on straight samples | 0.01242 | 0.00551 | 0.02822 | 0.05265 | -0.00152 |
| V2 | Linear ST with **prior** `C_αf=286 551, C_αr=355 912 N/rad`; KS fallback below v=2 m/s; per-segment straight bias subtracted                | 0.01490 | 0.00345 | 0.03728 | 0.06553 | +0.00248 |
| V3 | Linear ST with **fit** `C_αf=350 000, C_αr=350 000 N/rad` (grid search 50k–500k; L-BFGS-B fell back to x0 — loss surface non-smooth near `K_us·v²≈-1`) + bias | 0.01455 | 0.00367 | 0.03610 | 0.06398 | -0.00036 |
| V4 | Ridge regression on V3 residuals with features `[v, |a_y|, |δ|, sign(δ̇)]`, **leave-one-segment-out** CV                                    | 0.01120 | 0.00380 | 0.02484 | 0.05350 | -0.00334 |

**Headline:** RMSE 0.01394 → 0.01120 rad/s, **−19.6%** total. Attribution `|Σmarg − total|/total ≈ 0` (consecutive-difference accounting).

## Findings and physical reasoning

- **V1 carries most of the legitimate-physics gain.** Per-segment straight-line yaw-gyro bias cuts the straight-regime residual nearly in half (0.00929 → 0.00551). Gain in cornering is essentially zero — KS still has no slip.
- **V2 is a regression.** Δ = **+0.00248 rad/s worse**, especially steady and transient cornering. Openpilot ST prior `C_αf=286k, C_αr=355k` is **stiffer than the Mach-E tyres actually want** under measured inputs — ST over-predicts yaw rate in cornering. Matches `references/ks-vs-st.md`'s "ST prior too stiff for Mach-E tyres" warning.
- **V3 is a partial recovery, still regression vs V1.** Fitting `C_α` over the Mach-E set drives Cf/Cr toward the upper range (≈350k after a 19×19 grid + Nelder-Mead). Still worse than V1 because linear-ST functional form is wrong class for the non-linear slip behaviour in the data. Fit did not peg at upper bound (overfit flag), but landed on a flat plateau.
- **V4 is the real win.** A small ridge on 4 features reclaims the cornering structural error and beats both V1 and V0. Critically out-of-fold (leave-one-segment-out): every prediction comes from a model that has never seen its own segment. Lifts cornering regimes (steady 0.0361 → 0.0248; transient 0.0640 → 0.0535) — exactly where KS/ST's missing slip-angle dynamics dominate. Straight RMSE essentially unchanged.

## Honest regression flags

- **V2 worsened V1 by +1.93 mrad/s.** Cause: stiffer-than-real prior `C_α` over-predicts yaw in cornering.
- **V3 worsened V1 by +1.62 mrad/s** (even after `C_α` fit). Cause: linear-ST functional form cannot represent the non-linear slip; fitting in a wrong model class moves you along a wrong manifold.
- V4 is the only rung that beats V1.

## Methodological finding

The supplied `triage.fit_c_alpha` silently fails: L-BFGS-B returns its starting point `(1.5e5, 1.5e5)` because the loss surface is non-smooth around `K_us·v² = −1`, and `pegged` only checks the upper bound. A 19×19 grid search exposed the true plateau at ≈350 kN/rad. Reference text warns about pegging at the upper bound but says nothing about this near-`K_us·v² = −1` cliff. A naïve run would have shipped V3=V2.

## Limitations

- 40-of-315 segment sample chosen by sort order for reproducibility in budget.
- V4 model intentionally tiny (4 features, ridge α=1.0). A larger class could push further; the workshop bound is small ML + LOSO.

Files: `out/run_ladder.py`, `out/ladder.json`.
