# Module-4 / agent-03 (angle-C) — Lateral fidelity ladder

## Headline

Per-platform variant ladder on both Fords (Tesla excluded — no truth). Speed-known lateral-only KS contract held. Interleaved 4/1 train/test split; all RMSE numbers are held-out test RMSE.

- **F-150 Lightning:** 0.02037 → **0.01499 rad/s overall (-26%)**.
- **Mach-E:** 0.01613 → 0.01635 rad/s overall (**net regression**).

## Variants (per-platform fits, additive monotone)

| V  | DoF added                       | Mach-E overall | Lightning overall |
|----|---------------------------------|---------------:|------------------:|
| V0 | none (baseline)                 |    0.01613     |     0.02037       |
| V1 | constant `δ_offset`             |    0.01615     |     0.02015       |
| V2 | + understeer `K_us` (lin. bike) |    0.01639     |     0.01503       |
| V3 | + integer sample lag            |    0.01635     |     0.01499       |

Fitted: Mach-E `δ_off=-2.8e-4 rad, K_us=2e-4, lag=+1`; Lightning `δ_off=-7.8e-4 rad, K_us=4.5e-3, lag=+1`.

Per-regime test RMSE (V3): Mach-E 0.00825 / 0.03259 / 0.05974; Lightning 0.00521 / 0.02559 / 0.04392.

Marginals — Mach-E: V1 -1.3e-5 (regression), V2 -2.4e-4 (regression), V3 +4.1e-5. Lightning: V1 +2.2e-4, V2 +5.1e-3, V3 +4.2e-5. Attribution-coherence ≈ 0.00 on both (well under 0.15).

## Painful absence

Mach-E. The platform with the **best-tuned openpilot priors** (carParams direct from rlog) is where the linear-bicycle ladder runs out of headroom at the KS rung. V2 improves straight regime (0.00878→0.00828) but worsens steady and transient — `C_α` priors already over-encode understeer for steady cornering, and the transient residual is dominated by tyre-relaxation / actuator phase, which is ST-rung physics, not a KS tweak. Honest call: ship the Lightning fix, leave Mach-E alone at the KS rung.

## Near-misses

V3 (lag) lands at exactly **+1 sample (20 ms) on both platforms** — same direction, same magnitude. Almost certainly a `yaw_rate_meas` vs `delta_meas` capture skew in the measurement pipeline. Small effect (+4e-5) but cross-platform-consistent, more interesting than its size.

## Surprise

`evals/schema_check.py` **FAILS** on stored sim CSVs. Stored `yaw_rate_resid_rads = meas − pred`, not the convention's `pred − meas`. RMSE is unaffected (sign-squared away) so V0 stands — but this is exactly the failure ratchet item #1 was added to prevent. Bug lives in `code/generate_simdata_ford.py`. Flag for the team.

## RPI artifact paths

- `rpi/runs/20260527-160000/research.md`
- `rpi/runs/20260527-160000/plan.md`
- `rpi/runs/20260527-160000/implement-notes.md`
- `out/ladder/{FORD_MUSTANG_MACH_E_MK1.json, FORD_F_150_LIGHTNING_MK1.json, summary.json}`
- `tools/ladder.py`

## Eval status

- `baseline_rmse.py`: PASS, matches V0 above.
- `schema_check.py`: FAIL on stored CSVs (sign bug in generator).

## Skills used / authored

- Used: `skills/baseline-residual`, `skills/ablation-study`.
- Authored: none — both regressions were platform-specific physics ceilings, not recurring procedural failures.
