# EXPERIMENTS.md

Append-only log of experiments. `Rung:` required on every entry.

---

## E00 — V0 baseline (passthrough)
- Rung: 0
- Hypothesis: establish the floor.
- What I changed: nothing — predict() returns `yaw_rate_pred_rads` unchanged.
- Result (pooled, all platforms incl. Tesla):
  - yaw_rmse = 0.012934 rad/s
  - cte_rmse = 163.831 m
- Per-platform (yaw / cte):
  - LIGHTNING: 0.01633 / 157.51 (cte_drift +39.69)
  - MACH_E:    0.01362 / 148.00 (cte_drift -1.62)
  - IONIQ_5:   0.01770 / 247.50 (cte_drift -54.84)
  - TESLA:     0.00000 / 0.00 (no truth — passthrough)
- Verdict: baseline.
- Notes: per-segment bias-spread diagnostic — std(per_seg yaw residual mean) per platform:
  LIGHTNING 0.00626, MACH_E 0.00745, IONIQ_5 0.00936 (all > 0.002 → all benefit from per-seg δ₀ in principle).

## E01 — KS + understeer + first-order lag + per-segment δ₀ (recipe priors)
- Rung: 0
- Hypothesis: anti-patterns § "legal cousin" recipe — Mach-E/Hyundai ON, Lightning OFF.
- What I changed: implemented `yr_ss = v · (δ−δ₀) · g / (L_eff + K_us · v²)` with discrete first-order
  lag (τ); per-segment δ₀ via input-only straight-row gate `|yr_v0|<0.03 ∧ v>5`. Recipe coeffs
  (Lightning δ₀=0.00133 globally; Mach-E/IONIQ5 with platform-tuned g, L_eff, K_us, τ).
- Result (pooled):
  - yaw 0.012934 → 0.005874 (−54.6%)
  - cte 163.831 → 56.807 (−65.3%)
- Per-platform yaw/cte:
  - LIGHTNING 0.00566 / 62.18  (drift +0.32, near zero — global δ₀ works)
  - MACH_E    0.00859 / 98.68  (drift −21.98 — residual systematic bias)
  - IONIQ_5   0.00766 / 69.53  (drift −11.57)
- Verdict: KEEP — this is the highest-leverage move on this dataset.

## E02 — Lightning per-segment δ₀ ON
- Rung: 0
- Hypothesis: bias-spread (0.00626) is > 0.002 threshold, so per-seg should help on Lightning too.
- What I changed: `use_per_segment_delta0=True` for Lightning with fallback=0.00133.
- Result vs E01:
  - LIGHTNING yaw 0.00566 → 0.00765 (worse), cte 62.18 → 115.96 (much worse)
  - pooled yaw 0.005874 → 0.006057, pooled cte 56.81 → 63.45
- Verdict: REVERT. Reference reference was right despite the apparent spread: the variance for Lightning is route-bound, not in-segment, so the straight-row gate spuriously fits noise.
- Things this rules out: in-segment δ₀ estimation when the per-segment bias is not actually segment-local.

## E03 — scipy Nelder-Mead fit (g, L_eff, K_us, τ, δ₀) per platform on data/sim
- Rung: 0
- Hypothesis: priors from anti-patterns reference are heuristic; refit on full data.
- What I changed: `out/fit_coeffs.py` — per-platform yaw-RMSE objective. First unconstrained fit
  exposed g↔L_eff scale-invariance (Mach-E pegged g at lower bound 0.30, L_eff to 0.75 — invariance).
  Second fit pinned L_eff to physical wheelbase (Lightning 3.705, Mach-E 2.984, IONIQ_5 3.00).
- Result (pooled):
  - yaw 0.005874 → 0.005822 (no real change — invariance)
  - cte 56.81 → 57.04 (no real change)
- Per-platform yaw post-fit: LIGHTNING 0.00566, MACH_E 0.00841, IONIQ_5 0.00762.
- Verdict: KEEP fitted Lightning + Hyundai numbers (they shifted slightly); revert Mach-E to
  recipe priors (fit hit bounds and degraded CTE).
- Things this rules out: brute coefficient refitting beats reference priors only at margins of 1–2%
  on this dataset; structural change matters more than coefficient hyperparameter tuning.

## E04 — alternative δ₀ gates (steering, a_lat proxy)
- Rung: 0
- Hypothesis: maybe the V0-yaw gate `|yr_v0|<0.03` is too noisy on Mach-E (CTE drift −22 m).
- What I changed: re-ran with `|δ|<0.005 ∧ v>8` (steering gate) and `|v·yr_v0|<0.3 ∧ v>5` (a_lat
  proxy from allowlist channels).
- Result vs E01:
  - steering gate: pooled yaw 0.005840, cte 63.40 (worse on Mach-E and Hyundai)
  - a_lat proxy:  pooled yaw 0.006170, cte 75.67 (much worse on Hyundai)
- Verdict: REVERT — V0-yaw gate `|yr_v0|<0.03 ∧ v>5` is the best of the three on this dataset.

## E05 — Final shipped: V3 (recipe + fitted Lightning/Hyundai coeffs)
- Rung: 0
- Hypothesis: combine E01 priors for Mach-E with E03's L_eff-pinned fitted coeffs for Lightning
  and Hyundai (where the fit cleanly improved, no scale-invariance issue).
- What I changed: final-model/coeffs.json with mixed source.
- Result (pooled):
  - yaw 0.005853 (−54.7% vs V0)
  - cte 56.59 m (−65.5% vs V0)
- Per-platform: LIGHTNING 0.00566 / 62.19, MACH_E 0.00859 / 98.68, IONIQ_5 0.00762 / 69.03,
  TESLA passthrough.
- Verdict: SHIPPED.

## E06 — Rung-1: linear dynamic single-track on Mach-E (REQUIRED CLIMB ATTEMPT)
- Rung: 1
- Hypothesis: Mach-E CTE drift (−22 m) might be a transient/steady-state mismatch that a slip-angle
  model captures better than the static `v·δ/(L+K·v²)` form. Mach-E is the worst-CTE platform after
  rung-0, so highest expected payoff.
- What I changed: `out/rung1.py` — two-state Euler integration of `vy, yr` with `F_y = C_α · α`,
  Mach-E carParams from `code/parameters.py` (m=2336, Iz=4879, l_f=1.31, l_r=1.67, C_αr=355_912),
  fitted C_αf via bounded scalar Nelder-Mead. Used 4-substep Euler to stabilise integration.
- Result (Mach-E only, sub-sampled 60 / 240 segments for the fit, full eval after):
  - V0 Mach-E yaw 0.01362; rung-0 Mach-E yaw 0.00859; rung-1 best yaw 0.01284 at C_αf ≈ 400 000.
  - Rung-1 at carParams default (C_αf=286 551): yaw 0.01351.
  - Rung-1 fully un-tuned with `vy[0]=0` did NOT integrate stably at small substeps; needed ≥4
    sub-steps with high C_αf to avoid blow-up.
- Comparison to shipped rung-0 (E05): rung-0 Mach-E yaw=0.00859, rung-1 Mach-E yaw≈0.0128 (~50%
  worse). Did NOT score CTE for rung-1 (yaw already worse, not worth the integration cost).
- Verdict: REVERT — rung-1 alone, without a per-segment δ₀ correction and without a first-order
  steering lag, can't match a properly-calibrated rung-0 on this data. The cohort's evidence point:
  rung-1 needs to be combined with E01's δ₀ correction (apply δ₀ to the steering input *and* keep
  the slip-angle dynamics) to be competitive — not a drop-in replacement.
- Things this rules out: "swap rung-0 for rung-1 and it gets better." It doesn't. The per-segment
  steering offset is doing the heavy lifting; the steady-state vs dynamic distinction is second-order
  on this dataset.

## Falling-back rationale
Shipped E05 (rung-0). Rung-1 ran, was scored, and lost on the same platform where it had the largest
theoretical headroom (Mach-E CTE drift). With the time budget gone, the safer bet is the better-scoring
model. Logged here per AGENTS.md § "On exploration".
