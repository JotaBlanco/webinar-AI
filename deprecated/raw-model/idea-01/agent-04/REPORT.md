# Lateral-prediction improvement ladder — Ford KS model (agent 04)

## 1. Headline number

**Yaw-rate RMS residual** across all 545 Ford segments (Mach-E + F-150 Lightning), evaluated on held-out test split (50% of each segment):

| | rad/s | °/s |
|---|---|---|
| **Baseline V0** (raw, openpilot-canonical KS) | 0.01804 | **1.034** |
| **Final V4** (cleaned + lag + understeer) | 0.01191 | **0.682** |

**Total improvement: 34% reduction in RMS yaw-rate residual.**
If we strip out the data-hygiene step (which is not a model change), the model-only improvement is **20% reduction** on the clean subset (0.853 → 0.682 °/s).

## 2. What I implemented

The KS prediction is `ψ̇ = (v / L) · tan(δ)` with measured `v` and `δ` clamped at every step (speed-known lateral-only mode). I left the integrator alone and improved the prediction formula:

- **V1 hygiene** – mask out rows with `v ≤ 2 m/s`, `|a_lat_meas| > 20 m/s²`, `|ψ̇_meas| > 2 rad/s`. Pure data clean-up — no model change.
- **V2 steering bias** – fit a single global `δ_bias` (linearised least-squares using `sec²(δ)` derivative) on the train half and subtract: `tan(δ − δ_bias)`. Catches alignment / wheel-angle-sensor zero offset.
- **V3 transport lag** – integer-sample shift of `δ` (per segment, no boundary crossing) over `±10` samples at 50 Hz. Best lag was `τ = +3 samples = 60 ms` — measured steering leads the yaw response by ~60 ms, exactly the order of magnitude expected from rack + tyre transient.
- **V4 understeer gradient** – joint least-squares fit of `δ_bias` and an effective-wheelbase `K_us`: `ψ̇ = v / (L · (1 + K_us · v²)) · tan(δ − δ_bias)`. Fitted `K_us ≈ 4.4 × 10⁻⁴ s²/m²` — i.e. the kinematic model under-predicts lateral compliance at speed, exactly the gap a real bicycle/ST model fills.

All parameters were fit on the first half of each segment in time; metrics reported on the second half.

## 3. Attribution

**Scheme: sequential left-to-right.** Each step is evaluated *after applying all previous steps*. The "contribution %" is the share of the total RMS drop produced by that step:

| Step | RMS before | RMS after | Drop | % of total |
|---|---|---|---|---|
| V1 hygiene | 0.01804 | 0.01488 | 0.00316 | **51.5%** |
| V2 steering-bias | 0.01488 | 0.01477 | 0.00012 | 1.9% |
| V3 transport-lag (τ = 60 ms) | 0.01477 | 0.01437 | 0.00040 | 6.5% |
| V4 understeer + refit bias | 0.01437 | 0.01191 | 0.00246 | **40.1%** |

Order matters for sequential attribution. If you re-order, hygiene and understeer remain the two giants; bias/lag are second-order. Per-platform on V4: Mach-E 0.700 °/s, F-150 0.656 °/s — the truck is actually a touch easier to predict (longer wheelbase, less aggressive driving in the segments).

## 4. Surprises

- **Two F-150 segments had stationary vehicles with `a_lat_meas` blowing up to 1057 m/s²** (`112e4d6e0cad05e1/.../00000016--300e9e8ccb/0` and `.../00000004--c2ebfcbf0d/0`). Almost certainly a CAN/sensor bring-up artefact when stationary. They poisoned the unfiltered F-150 a_y RMS to ~10.9 m/s². The yaw-rate channel was fine on the same rows. Strong argument for keeping `a_y` and `ψ̇` as separate metrics.
- **Steering bias is essentially zero** (0.014° road / 0.23° steering-wheel). The openpilot zero-offset is well calibrated. I expected a few tenths of a degree.
- **Transport-lag is small in absolute terms (40 e-5 RMS drop)** but consistent — it picked `+3 samples = 60 ms` deterministically, and it's a free improvement.
- **Understeer is by far the biggest pure-model effect.** A single scalar `K_us = 4.4 × 10⁻⁴ s²/m²` (same value across both platforms in my joint fit) recovers 40% of the total drop. That's effectively the message: a bicycle/ST model would justify itself if K_us doesn't generalise per-platform.

## 5. Limitations

- I did not retrain `K_us` per platform — would expect Mach-E and F-150 to want different values. Easy next step.
- I did not attribute the `a_y` metric — the F-150 stationary glitches required a hygiene mask first, and the headline question was about lateral prediction more broadly so I picked yaw-rate as cleaner. `a_y` after V4 should drop comparably since `a_y = v · ψ̇` under the clamps.
- I did not re-run the integrator — every "improvement" is post-hoc arithmetic on the existing CSVs. That's fine for KS in speed-known mode (since the only state contributing to `ψ̇` is the clamped `δ`), but a real ST model with `β` and `ψ̇` as integrated states would need re-integration.
- I treated `K_us` as global; one could fit `K_us` per (platform, v-bin) and recover more.
- I did not explore: (a) steering-rate / `δ̇` feed-forward, (b) low-pass-filter mismatch between measured `a_y` (5 Hz cutoff per adapter) and predicted (no filter), which could be biasing the a_y residual.
- I had no access to the canonical solution / observations / sibling reports / cross-angle modules (and didn't try). I never attempted to read those.

## 6. Files produced

- `tools/baseline.py`
- `tools/ladder.py`
- `out/ladder_run.txt`

```
ISOLATION_REPORT:
read_outside_allowed: []
attempted_blocked: []
shared_dir_writes: []
notes: "Stayed within ./code, ./data, and own folder. No hook blocks triggered. Did not attempt sibling, webinar-angle-*, or webinar-00 reads. Skipped TodoWrite per instructions; two reminders ignored as task was short and linear."
```
