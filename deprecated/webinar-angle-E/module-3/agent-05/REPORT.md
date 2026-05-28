# REPORT.md — webinar-angle-E / module-3 / agent-05

## Platform & contract

- Platform: **FORD_MUSTANG_MACH_E_MK1**
- Truth channel: `yaw_rate_meas_rads` (measured), with `v` and `δ_road` **clamped to measured** (`clamp_v_to_measured=True`, `clamp_delta_to_measured=True`). Speed/steering state agreement is zero by construction; the only metric is the lateral residual `yaw_rate_pred_rads − yaw_rate_meas_rads`.
- Corpus: 913 626 samples across 315 `sim.csv` files (regime split: 785 093 straight / 106 978 steady / 21 555 transient).
- Skill used: `yaw-divergence-triage` (V0 → V1 → V2 → V3 ladder) composed with `regime-comparison` for per-regime attribution.

## Headline

**V1 (KS recalibrated with per-segment straight-line gyro-bias subtraction) is the only change that improves lateral fidelity.** Overall RMSE drops from **0.01613 → 0.01469 rad/s** (−8.9 %). V2 and V3 both regress — physically, they push toward more understeer than these tyres actually have, and the static linear single-track gain has no way to express the transient-cornering structure that dominates the remaining error.

## Variant ladder (RMSE of `ψ̇_pred − ψ̇_meas`, rad/s)

| variant | overall | straight | steady   | transient | marginal Δoverall | attribution | flag |
|---------|---------|----------|----------|-----------|--------------------|-------------|------|
| V0 (CSV residual as-is)                | 0.01613 | 0.00877 | 0.03173 | 0.05680 | —          | baseline                          |   |
| V1 (KS, canonical L, segment gyro-bias) | 0.01469 | 0.00493 | 0.03168 | 0.05730 | **−0.00143** | **gyro-bias correction on straights** | small uptick on transient (+0.0005) |
| V2 (Linear ST, prior C_α)              | 0.01653 | 0.00701 | 0.03450 | 0.06234 | **+0.00184** | ST understeer overshoot           | **REGRESSION** vs V1 on all 3 regimes |
| V3 (Linear ST, fitted C_α)             | 0.01664 | 0.00700 | 0.03482 | 0.06266 | **+0.00011** | optimizer cannot move (see Surprise) | **REGRESSION** vs V1; effectively pegged |

Attribution scheme: strict marginal, fixed order V0→V1→V2→V3, marginal = `RMSE(V_{i-1}) − RMSE(V_i)`. Marginals sum to −0.000508; total drop V0→V3 = −0.000508; reconciliation = 1.0000 (well inside the 15 % tolerance).

## Per-regime contrast vs V0 (sibling skill `regime-comparison`)

| variant | Δ straight | Δ steady  | Δ transient | dominant regime |
|---------|------------|-----------|-------------|------------------|
| V1      | **−0.00384** | −0.00005 | +0.00050    | straight         |
| V2      | −0.00176     | +0.00276 | +0.00555    | transient        |
| V3      | −0.00177     | +0.00309 | +0.00586    | transient        |

The dominant-regime column localises every variant's effect: V1's win is **all in straights** (a gyro-bias removal, not a tyre-model improvement). V2 and V3 each cost the most in **transient** — the regime where the static-gain ST formulation has no degrees of freedom (no `I_z`, no yaw-lag time constant, no slip-angle dynamics).

## Honest regression flags

- **V2 worse than V1 on every regime.** Cause: `K_us` from openpilot's prior `(C_αf=286 551, C_αr=355 912 N/rad)` shrinks the steady-state yaw-rate gain `v·δ / (L·(1+K_us·v²))`. Measured yaw is closer to the kinematic value than to the prior-ST value, so the understeer term over-corrects.
- **V3 worse than V2 and V1.** Cause: the L-BFGS-B fit does not move from its initial value at default `eps`. A 5-seed multi-start (1.5e5,1.5e5 / 5e4,5e4 / 5e5,5e5 / 2.8e5,3.5e5 / 1e5,3e5) returns each seed unchanged. Loss is monotone-decreasing toward the upper bound; best is `(5e5, 5e5)` at 0.01632 — i.e. **the fit is asking for `K_us → 0`, which is just KS.** ST is structurally the wrong family here, not under-tuned. The skill's `pegged` flag is upper-bound-only and so reports `pegged=False`, but functionally V3 is pegged high.

## What's still painful (would unblock the transient column)

- No timestamp-aligned **lateral-acceleration channel** in `sim.csv`, so no way to estimate bank/grade and subtract a road-induced gyro contribution from `yaw_rate_meas_rads` in cornering.
- No **dynamic** ST (yaw-rate state with `I_z` and a yaw-lag time constant) — the static gain has no mechanism for the transient lag responsible for the 0.057 rad/s transient floor.
- No per-segment fit (one global `C_α` pair across 315 segments hides tyre/load variation).

## Variant deltas — concise

- **V1 contributes −0.00143 rad/s overall** — the entire usable improvement.
- **V2 contributes +0.00184 rad/s (regression)** — prior-tyre understeer mismatch.
- **V3 contributes +0.00011 rad/s (further regression)** — degenerate fit; ST model wrong family.
- **Net V0 → V3: +0.00051 rad/s (regression).** **Recommendation: ship V1, discard V2/V3.**
