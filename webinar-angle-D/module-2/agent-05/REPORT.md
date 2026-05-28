# REPORT — webinar-angle-D / module-2 / agent-05

**Task:** lateral-fidelity-challenge (improve lateral / yaw-rate prediction of the KS model on Ford segments, attribute the gain).
**Skill:** `lateral-fidelity-triage` v0.1 (first crystallisation).

## Scoring substrate

- **Platform:** `FORD_MUSTANG_MACH_E_MK1` (Mach-E). Per the skill's "Truth-channel discovery" rule, Mach-E is the default Ford pass; both Fords carry decoded IMU truth, Tesla does not.
- **Truth channel:** `yaw_rate_meas_rads` — **measured** (Ford IMU, decoded from party DBC in the rlog). Not a prediction.
- **Operating contract:** `clamp_v_to_measured=True`, `clamp_delta_to_measured=True`. `v` and `δ_road` are inputs; the only thing under test is the lateral-state map `(v, δ_road) → ψ̇`.
- **Segments:** first 20 Mach-E `sim.csv` files (sorted, deterministic) → **57,979 rows**.
- **Sign check:** `corr(δ_road, ψ̇_meas)` on cornering rows (|δ|>0.02): **+0.943** → sign convention is correct, no flip needed.

## Variant ladder

All numbers are RMSE of `(ψ̇_pred − ψ̇_meas)` in rad/s. Per-segment straight-line gyro bias is subtracted on V1/V2/V3 per the skill's V1 rule.

| Variant | Overall | Straight | Steady | Transient | Δ vs prev | % vs prev |
|---|---:|---:|---:|---:|---:|---:|
| V0  baseline (as-shipped `yaw_rate_resid_rads`)            | 0.01575 | 0.01095 | 0.04411 | 0.06379 | —          | —         |
| V1  KS recal (`L=2.875`) + per-seg straight-line bias      | 0.01368 | 0.00662 | 0.04522 | 0.06738 | −0.00207   | **−13.2%** |
| V2  Linear-ST, prior C_α (286.5k / 355.9k)                 | 0.01606 | 0.00351 | 0.06072 | 0.08514 | +0.00238   | +17.4%    |
| V3  Linear-ST, fit C_α (multi-start; 3.0e5 / 3.0e5)        | 0.01581 | 0.00368 | 0.05953 | 0.08367 | −0.00025   | −1.5%     |
| V4  V3 + Ridge residual learner (LOO over segments)        | 0.01499 | 0.00376 | 0.05453 | 0.08119 | −0.00082   | −5.2%     |

**End-to-end:** V0 → V4 = **0.01575 → 0.01499 rad/s, −4.8% RMSE.**

## Attribution

| Step | Mechanism | Where it helps | Where it hurts | Δ overall RMSE |
|---|---|---|---|---:|
| V1 | canonical wheelbase + per-segment yaw-gyro bias removal | straight-line (×0.60) | cornering very slightly worse (geometric KS still no slip) | **−13.2%** |
| V2 | linear-ST steady-state gain replaces tan(δ) geometry | straight-line (×0.53 vs V1) | steady (+34%) and transient (+26%) — linear-ST under-predicts cornering yaw on Mach-E | **+17.4%** |
| V3 | C_α fit on whole segment set (multi-start; helper as-shipped is broken — see below) | marginal vs V2 | barely moves the needle: priors were close to the symmetric-fit optimum | **−1.5%** |
| V4 | Ridge residual learner over `[v, |a_y|, |δ|, sign(δ̇)]`, LOO-CV | steady (−8.4% vs V3) and transient (−3.0% vs V3) | straight-line (+2%) — learner over-corrects when error is already small | **−5.2%** |

Net contributions to the −0.000754 rad/s overall improvement:
- V1 (KS recal + bias): **−0.00207** → contributes **+274%** of the net (i.e. it does all the work and then some).
- V2 + V3 combined: **+0.00214** (net regression).
- V4: **−0.00082** (claws back roughly what V2 cost on cornering).

The skill's ladder, taken end-to-end on Mach-E, is **front-loaded**: nearly all the win is in V1; V2/V3 trade straight-line accuracy for cornering accuracy in the wrong direction; V4 partially repairs that trade.

## Findings on the skill itself (v0.1, first crystallisation)

1. **`triage.fit_c_alpha` is broken in practice.** It runs a single L-BFGS-B from `x0=(1.5e5, 1.5e5)` on a non-convex loss with cliffs where `1 + K_us·v²` crosses zero. The optimizer returns x0 unchanged. A 5×5 grid multi-start finds the actual minimum at (3.0e5, 3.0e5), RMSE 0.01735 vs single-start 0.02. **Patch needed:** multi-start, or random-restart, or trust-region.
2. **No regime-weighted fit.** The C_α fit minimises overall RMSE, dominated by straight-line samples where the linear-ST gain is nearly insensitive to C_α. A cornering-only fit would be the obvious v0.2 patch.
3. **No KS↔ST handoff rule.** Skill says "below `v_min`, fall back to KS" — fine — but no rule for when KS is better than ST *above* `v_min`. On this data, KS+bias (V1) **beats** linear-ST (V2/V3) on cornering. The skill walks the ladder upward by definition; the operator needs a "stop here" criterion.
4. **No held-out segments.** V0–V3 are all fit-and-score on the same 20 segments. Only V4 has a LOO-CV protocol. A v0.2 patch should mandate a train/eval split for the C_α fit too.
5. **Attribution is per-step, not orthogonal.** The table above reports `Δ overall RMSE` between consecutive variants. That's what the skill prescribes, but it's order-dependent: V3 looks weak because V2 already moved the needle the wrong way. Shapley-style or all-subsets attribution would be more informative.
