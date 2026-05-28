# Phase 2 — Plan (locked)

## Platform
**FORD_MUSTANG_MACH_E_MK1.** Cleaner residual mean (-2.3e-4 vs Lightning -3.6e-3), larger sample (913 k rows / 315 files), and smaller low-v fraction (11 % vs 17 %) — so the ladder demonstrates physics improvements rather than ST→KS fallback bookkeeping. Lightning's louder bias story is interesting but noisier for a four-rung ladder demo.

## Variant ladder (fixed order, marginal RMSE accounting V_{i-1}→V_i)
- **V0** — baseline `yaw_rate_resid_rads` from sim.csv as-is. No preprocessing.
- **V1** — KS recalibrated: `ψ̇ = v·tan(δ_road)/L` with canonical L from `parameters.py`, minus per-segment yaw-gyro bias = mean residual on `|δ_road|<0.01` samples.
- **V2** — Linear ST with openpilot **prior** `C_αf, C_αr`: steady-state bicycle gain `v·δ/(L·(1+K_us·v²))`. KS fallback below v_min=2 m/s.
- **V3** — Linear ST with **fitted** `C_αf, C_αr` (bounded 5e4–5e5 N/rad, pooled over the segment set, minimise pooled RMSE). Flag pegged-bound regressions.

## Attribution scheme
Strict marginal, fixed order V0→V1→V2→V3. Per variant `ΔRMSE_i = RMSE(V_{i-1}) − RMSE(V_i)`. Check sum-of-marginals reconciles to total drop within 15 %. Report regressions (negative ΔRMSE) as such, with physical cause.

## REPORT.md shape
- Headline (platform + overall RMSE drop V0→V3).
- Operating contract (truth column, clamps).
- Variant ladder table — columns: variant, RMSE overall, RMSE straight, RMSE steady, RMSE transient, ΔRMSE marginal, attribution note.
- Attribution accounting check (sum vs total).
- Regime-comparison sub-table (sibling skill output) — per-variant Δ-vs-V0 per regime + dominant regime.
- Regression flags (pegged-bound, etc.).
- "Which phase surfaced which decision" note (RPI evidence).
- Plan dissent (only if Phase 3 disagreed with this plan).

## Out of scope (considered & rejected)
- **V4 residual learner (GBM on residual)** — task is "tell me how much each change contributed"; a learner muddies attribution and the skill ladder stops at V3.
- **Per-segment C_α fit** — too many free parameters for the segment count; pooled is what the skill prescribes.
- **Lightning as primary platform** — see platform choice rationale; could appendix later if time permits, not in this run.
- **Unclamping v/δ to "fix" speed-state agreement** — explicitly forbidden by the operating contract.
- **Non-linear ST / tyre saturation model** — out of skill scope.
