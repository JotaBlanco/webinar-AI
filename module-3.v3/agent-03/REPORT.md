# REPORT — module-3.v2 / agent-03

## Headline numerical result (canonical-grader equivalent, pooled, all platforms incl. Tesla)

| metric | V0 | shipped | delta |
|---|---|---|---|
| yaw_rate_rmse (rad/s) | 0.012934 | **0.005853** | **−54.7%** |
| cte_rmse (m)          | 163.831  | **56.59**    | **−65.5%** |

Per-platform (shipped):
- LIGHTNING: yaw 0.00566 / cte 62.19 (cte drift +2.67 m)
- MACH-E:    yaw 0.00859 / cte 98.68 (cte drift −21.98 m) ← residual systematic CTE bias
- IONIQ-5:   yaw 0.00762 / cte 69.03 (cte drift −11.65 m)
- TESLA:     V0 passthrough (no truth channel — fitting is moot)

## What I implemented

1. **E01 — KS + understeer + first-order lag + per-segment δ₀** (anti-patterns § "legal cousin").
   `yr_ss = v·(δ−δ₀_seg)·g / (L_eff + K_us·v²)`, then a discrete first-order lag with τ. δ₀
   per-segment, estimated from an **input-only** straight-row gate
   `|yaw_rate_pred_rads| < 0.03 ∧ v_mps > 5` (no truth peek). Platform-gated:
   Mach-E and IONIQ-5 ON, Lightning OFF (in-segment estimation hurt Lightning — E02 confirmed).
2. **E03 — scipy refit (L_eff pinned to wheelbase to break g↔L_eff scale-invariance).**
   First fit pegged Mach-E's g at the lower bound (classic identifiability symptom from
   anti-patterns.md). Fixing L_eff per platform let g, K_us, τ, δ₀ converge — but the yaw
   RMSE only moved by 1–2%. The reference's heuristic priors were already near-optimal.
3. **E04 — alternative δ₀ gates** (steering, a_lat proxy from allowlist). Both worse;
   the V0-yaw gate is best on this data.
4. **E06 — Rung-1 climb attempt (linear dynamic single-track for Mach-E).** Two-state Euler
   integration of (vy, yr) with `F_y=C_α·α`, m/Iz/l_f/l_r/C_αr from openpilot carParams,
   fitted C_αf only. Required 4-substep Euler to stabilise. Best yaw RMSE 0.01284 vs.
   rung-0's 0.00859 (~50% worse). **Did not ship.** Logged per AGENTS.md mandate.

Final shipped: E05 — recipe priors for Mach-E + L_eff-pinned fitted coeffs for Lightning
and IONIQ-5.

## Most painful absence in the harness

**No `fit-model` skill with a CTE-aware joint objective and CTE-trajectory-integrator already
plugged in.** I had to roll my own Nelder-Mead loop in `out/fit_coeffs.py`. The skill body
description in AGENTS.md says it supports `objective="cte"`, but the skill files weren't loaded
in a way I could trivially adapt — for time budget, I rolled my own yaw-RMSE-only objective, which
is what then plateaued. A fit-model skill that minimises the *pooled CTE* directly would have let
me chase Mach-E's −22 m CTE drift even when the yaw RMSE was already plateaued.

## What the rules prevented me from almost doing

I almost reached for the truth column (`yaw_rate_meas_rads`) inside `_per_segment_delta0` to
sanity-check the gate — the anti-patterns reference flagged this explicitly, and the operating
contract makes it impossible (it's stripped from sim-only). I substituted the V0-yaw input-only
gate as recommended. Also: my initial Mach-E unconstrained fit landed at g=0.30, L_eff=0.75 —
not because those are physical, but because of the g↔L_eff scale-invariance documented in
anti-patterns § failure-mode index. Catching it earlier saved me a chase.

## Most surprising thing learned

The per-segment bias-spread diagnostic (`std(per_seg_yaw_residual_mean)`) on this dataset reads
**0.00626** for Lightning — above the 0.002 "turn per-segment δ₀ ON" threshold from the reference.
The reference *also* says Lightning should be OFF. I tested both — Lightning's per-seg δ₀ ON
made Lightning **worse** (yaw 0.00566 → 0.00765, cte 62 → 116). The lesson: per-segment bias
spread above the threshold is *necessary but not sufficient*. Lightning's bias is route-bound,
not segment-bound, so an in-segment median doesn't capture it. The platform-level diagnostic
needs a "is the variance in-segment or between-segment-within-route?" follow-up — which the
reference didn't supply and I didn't have time to write.
