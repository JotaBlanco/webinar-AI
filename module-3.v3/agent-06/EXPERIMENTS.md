# EXPERIMENTS.md

Append-only log of attempts. One entry per concrete attempt.

## Alternatives considered

- (structure) **Residual-learner on V1** — ridge linear regression of (V1 − truth) on allowlist features {yr_v1, |yr_v1|, v, v·yr_v1, dδ/dt, δ, 1}. Attacks: per-platform gain bias + transient signed bias.
- (structure) **Linear dynamic single-track (rung 1)** — proper (vy, yr) ODE with linear tyres, RK4 sub-stepped. Attacks: transient regime where V1's first-order lag is a band-aid.
- (structure) **Regime-switched composite** — V1 in straight-line/steady, dynamic-ST in transient. Attacks: V1's lag underfit on `|dδ/dt|>0.05` rows. *(Not built — superseded once residual-learner already covered the structurally-different requirement and won; in the time budget, building this fourth was not worth the risk.)*
- (structure) **Complementary filter** blending V1 yaw with a high-pass of δ̇·g / L_eff. Attacks: V1's lag induces phase error on fast steering. *(Sketched; not built — same reason as above.)*
- (refines-v1) **Affine post-correction** `y = a·yr_V1 + b` per platform — sanity refit of V1 to absorb gain error. Tagged refines-v1 because it cannot reach states V1 cannot.

---

## E00 — V1 baseline

- Hypothesis: confirm the floor.
- Result (dev pooled): yaw 0.005874; CTE 56.81.
- Per-platform: Lightning 0.00566 / 62.2; Mach-E 0.00859 / 98.7 (CTE drift −22 m 🚨); IONIQ-5 0.00766 / 69.5 (CTE drift −11.6 m ⚠️); Tesla 0/0.
- Verdict: baseline. Residual diagnosis: CTE is dominated by signed yaw bias, not noise. corr(V1 residual, yr_v1) = +0.34 on Mach-E → V1's gain is too high.

## E01 — affine-v1 (refines-v1, benchmark)

- Model dir: models/affine-v1/
- Hypothesis: if V1's residual is dominated by a per-platform gain error, an affine `y = a·yr_v1 + b` should remove most of it.
- What I did: per-platform OLS on truth vs V1 yr (v>5 m/s), 300 segs/platform.
- Result (dev pooled): yaw 0.005874 → 0.005859 (−0.3%); CTE 56.81 → 54.98 (−3.2%).
- Verdict: keep as benchmark — confirms gain hypothesis. Subsumed by E03.

## E02 — dynamic-st rung-1 (structure)

- Model dir: models/dynamic-st/
- Hypothesis: replace V1's steady-state + first-order lag with the actual linear lateral dynamics ODE (vy, yr).
- Build notes: explicit RK4 at 20 ms exploded at openpilot C_αf=286 kN/rad priors (exactly the failure mode `references/dynamics-formulations.md` warned about). Fixed by sub-stepping to 2.5 ms inside each 20 ms tick. Added per-platform affine post-fit on the output to absorb gain mismatch.
- Result (dev pooled): yaw 0.005874 → 0.006549 (+11%); CTE 56.81 → 58.98 (+4%).
- Verdict: shelve for this iteration. Root cause: V1's K_us was *fit* on this data (≈0.0015 Mach-E, 0.0035 Lightning), whereas the rung-1 effective K_us_dyn derived from carParams is ~0.0017 across the fleet — i.e. lower. The dynamic ST is under-parameterised relative to the *fitted* V1, not the *theoretical* V1. With time, the right move is fitting C_αf, C_αr, Iz directly instead of using carParams. The cohort failure mode in m3.v2 was real.

## E03 — residual-learner (structure, shipped)

- Model dir: models/residual-learner/
- Hypothesis: V1's residual is well-approximated by a low-dim linear combination of allowlist features — fit it, subtract it.
- What I did: per-platform ridge regression with features [yr_v1, |yr_v1|, v, v·yr_v1, dδ/dt, δ, 1]. Trained on first 70% of segments per platform. Swept λ ∈ {0.001 … 3000}; best around λ=30 (yaw lowest, CTE within 0.5 m of its minimum).
- Result (dev pooled): yaw 0.005874 → **0.005770** (−1.8%); CTE 56.81 → **53.78** (−5.3%).
- Per-platform CTE drift: Lightning +0.3 → +2.3 m; Mach-E −22.0 → **−8.9** m; IONIQ-5 −11.6 → **+1.9** m.
- Verdict: SHIPPED. Cleanest residual diagnosis is the simplest tool — a 7-coef linear correction beats a rung-1 ODE with 6 physical parameters because the correction directly targets V1's actual error structure rather than redoing V1's job.
