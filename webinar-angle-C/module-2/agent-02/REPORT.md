# Module-2 / agent-02 (angle-C) — Lateral fidelity

**Platform:** `FORD_MUSTANG_MACH_E_MK1` (Tesla excluded per AGENTS.md rule 4 — no decodable yaw-rate truth).
**Truth:** `yaw_rate_meas_rads` (measured, Ford IMU).
**Contract:** `v` and `δ` clamped to measured per rule 5; only ψ/ψ̇/a_y/x/y predicted.

**Headline.** Mach-E lateral RMSE improves from **16.13 → 15.53 mrad/s** (~3.7%, all-regime, interleaved held-out). All gain lives in V2 (a single per-platform gain k=1.069). V1 bias and V3 lag are essentially noise. Cornering regimes are where the model is actually broken: transient RMSE **57.8 → 49.6 mrad/s (~14%)**.

## Variants

Strict marginal, V0→V3, 315 segments, every-5th-sample held-out test (interleaved per AGENTS.md §7); pred−meas convention; a_y re-derived as v·ψ̇ per §9:

| variant | all | straight | steady | transient | note |
|---|---|---|---|---|---|
| V0 baseline | 16.13 | 8.59 | 40.39 | 57.80 | raw KS |
| V1 bias | 16.14 | 8.56 | 40.45 | 57.91 | bias = +0.75 mrad/s |
| V2 gain | 15.58 | 9.22 | 37.87 | 51.16 | k = 1.0687 |
| V3 lag | 15.53 | 9.18 | 37.99 | 49.58 | +1 sample (+20 ms) |

(units mrad/s; fits per-platform Mach-E pool, not per-segment, per §8.)

## Painful absence

No tyre-slip term. KS is geometric (`ψ̇ = v·tan(δ)/L`); the missing factor of ~1.07 is exactly the linear-tyre understeer correction. A gain is a one-parameter proxy for the ST cornering-stiffness terms — the right next move is to swap KS for ST and refit C_α, not climb the gain ladder further.

## Near-misses / regression

V2 worsens the **straight** regime (8.59 → 9.22): scaling pred by 1.069 amplifies KS's small-amplitude noise where there's nothing to correct. A regime-gated gain (apply k only when |ψ̇_meas| > 0.05 rad/s) would recover ~0.05 mrad/s on straights. Flagged per §9: a_y was re-derived; V3 a_y test RMSE = 0.363 m/s².

## Surprise

The bias is ≈0 (0.75 mrad/s, below the regression noise floor). KS has no static yaw offset — it's a clean **gain** error, not an **offset** error. AGENTS.md §1 warns about sign-flipped bias; here the bias step is just inert. Also: best lag is +1 sample (20 ms) — within sensor-pipeline tolerance, not a physical phase error.

Files: `tools/ladder.py`, `out/ladder.csv`.
