# Module 2 / Agent 10 — Lateral fidelity

## Headline (full data/sim/segments, n=1996)

| Variant | Yaw RMSE (rad/s) | CTE RMSE (m) |
|---|---|---|
| V0 — kinematic single-track (workshop wheelbases) | 0.01413 | 169.61 |
| **Final — steady-state single-track per platform** | **0.00649** | **79.89** |

54% drop in yaw RMSE, 53% drop in CTE.

Per-platform yaw / CTE (final): Tesla 0.00000 / 0.00 (Tesla truth IS the KS prediction — see note 5), Mach-E 0.00895 / 123.26, Ionic-5 0.00865 / 108.54, F-150 Lightning 0.00617 / 61.51.

Route-grouped 80/20 dev (held-out routes, fit on train): yaw 0.00859, CTE 75.63. Train-vs-dev gap is small, so the per-platform coefficients are not overfit at the route level.

## Variants implemented

1. **V0 (baseline)** — `(v/L)·tan(δ_road)` with per-platform wheelbase. Reference only.
2. **Final** — per-platform `yr = v·tan(g·δ_road + δ₀) / (L_eff + K·v²)`. Four scalars per platform (L_eff, K, δ₀, g) fit by Levenberg-Marquardt on the route-grouped train split.
   - This is the steady-state bicycle-with-understeer formula. K absorbs cornering-stiffness / load-transfer / OEM steering-comp behaviour without needing tyre data; gain absorbs whatever the steering-ratio adapter under-reported; δ₀ absorbs steering offset.
   - Tesla degenerates to V0 because in `data/sim/segments` the Tesla "truth" channel `psi_dot_rads` is itself the workshop KS output — there is no recorded yaw to fit against.

## Most painful absent component

A **canonical-grader stub I could run against `sim-only/segments/`**. I had `score-model/` for sim/ and a hand-rolled `score_final.py`, but to confirm I matched the grader contract I had to reverse-engineer it from the contract description in the operating notes. With ~20 platforms missing CAN columns and a Tesla schema that doesn't even have `yaw_rate_meas_rads`, a one-line grader-parity script would have saved ~10 minutes of confusion.

Runner-up: the `pre-flight-final-model` skill looks for `data/sim-only/<PLATFORM>/**/sim.csv` but the actual layout is `data/sim-only/segments/<PLATFORM>/**/sim.csv` — so the shape check silently *skips*. Worth a one-line fix in the skill.

## Rules-prevented temptations

- Wanted to peek at the canonical grader source / a sibling agent's predict for sanity. Did not.
- Tesla's V0-perfect dev score is suspicious; I wanted to look at module-1 or `_grade` to see whether the canonical grader uses a different Tesla truth source than `psi_dot_rads` (perhaps an IMU stream). I declared this as a limitation here instead.

## Most surprising thing

The Ford Mustang Mach-E's fitted **gain = 1.37** — i.e. the published openpilot steering ratio under-estimates effective δ_road by 37%. F-150 and Ionic-5 have gain near 0.9, and Tesla 1.00. So a chunk of the V0 yaw error wasn't a missing tyre model — it was the steering-ratio metadata being wrong (or the adapter applying it wrong) on the Mach-E. A four-parameter fit per platform was enough to halve both KPIs without ever touching tyre stiffness.

## Limitations / honesty

- Tesla yaw RMSE of zero is an artefact of the dataset: `psi_dot_rads` in Tesla's `sim.csv` is `(v/L)·tan(δ)` already. If the canonical grader uses a different truth source (e.g. IMU), the V0 and Final Tesla numbers will both rise, but the relative ordering is unaffected by my model since I fit-degenerate to V0 there.
- I did not implement a CTE-specific objective; the gain comes entirely from yaw-rate improvement propagating through trajectory integration. A path-curvature-aware fit (weighting low-frequency δ harder) could push CTE further.
- No transient/lag model — purely steady-state. A first-order yaw-rate lag would likely help the Mach-E where residual std is highest.

ISOLATION_REPORT:
```
read_outside_module: []
attempted_blocked: []
shared_dir_writes: []
notes: "All reads under module-2/agent-10/ subtree (incl. code/ and data/ symlinks). Did not Write REPORT.md per harness rule — body returned inline. Verified contract by calling predict() directly on data/sim-only/segments samples for all four platforms."
```
