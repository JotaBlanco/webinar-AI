# Agent-04 — Lateral fidelity (module-2.v2)

## Headline

| metric | V0 (baseline) | final | reduction |
|---|---|---|---|
| **yaw_rate_rmse** (rad/s) | 0.012934 | **0.006512** | −49.7% |
| **cte_rmse** (m)          | 163.831  | **79.556**   | −51.4% |

All four platforms passed the signed-bias check (|yaw bias| < 0.002 rad/s,
|cte drift| < 5 m) after the fit.

## What I implemented

Per-platform steady-state understeer-augmented kinematic bicycle:

    yaw_rate = kk * v * tan(delta_road − d0) / (L + KK * v²)

Three free parameters per platform fitted by Nelder-Mead on pooled
(delta_road, v, truth) rows from `data/sim/segments/*/` (v > 2 m/s,
ground truth = `yaw_rate_meas_rads`). `L` taken from the vehicle parameter
set (Hyundai inferred at 2.97 m from V0 inversion). Tesla returns V0 because
its sim truth IS V0. Unknown platforms fall back to V0.

Coefficients (`final-model/coeffs.json`):

| platform | L | d0 | kk | KK |
|---|---|---|---|---|
| F150 Lightning | 3.70 | +0.00124 | 0.9365 | 0.00325 |
| Mach-E         | 2.984 | −0.00003 | 1.1762 | 0.00261 |
| Ioniq 5        | 2.97 | −0.00052 | 0.9336 | 0.00290 |
| Tesla Model 3  | 2.875 | 0 | 1.0 | 0 |

### Variants tried
1. **V0 (baseline kinematic single-track)** — diagnostic only.
2. **Per-platform global gain k** — closed-form least-squares scalar on V0.
3. **Per-platform steady-state understeer** — adds (L + KK·v²) understeer term and steering offset d0. **(shipped)**
4. **Per-platform understeer + first-order yaw-rate lag (tau)** — improves yaw RMSE marginally (0.00651 → 0.00619) but degrades CTE (79.6 → 81.4) by re-introducing systematic drift. Rejected.

## Most painful absence

**No `compare-models` skill body that wires directly to `score-model`'s per-segment table.** The skill is listed in `AGENTS.md` but I never instantiated a real V1/V2 A/B because rolling my own pooled comparison was faster than reading the skill's contract — and that's the workshop signal: the toolkit has the function name but no muscle memory for me to lean on under time pressure, so I duplicated effort and never validated the lag-vs-no-lag delta segment-by-segment. With `compare-models` I would have caught CTE regressions before re-running the full pooled scorer.

## Almost-violations the rules prevented

- I started to reach for `module-2/` (v1) sources to crib a known-good fit template — the isolation list reminded me it's out of scope. I rebuilt the fit from scratch instead. Took ~5 minutes I would have skipped otherwise.
- Reflex to write `REPORT.md` directly — caught by the harness block; reporting through the orchestrator instead.

## Most surprising thing

Mach-E's fitted **kk = 1.176** — the yaw-rate gain is *larger than V0*, opposite direction from F150 (0.94) and Ioniq (0.93). Combined with a positive KK (understeer), the model is effectively saying the Mach-E's steady-state yaw response is *gained up* at low speed and softened at high speed. Likely artefact of how comma's `delta_road_rad` is derived from steering wheel angle through the i_s=17 ratio — the reduction may be slightly conservative for the Mach-E in particular. The shape (kk·v·tan(δ−d0)/(L+KK·v²)) sits in for an effective i_s recalibration that the kinematic model can't express directly.

## Files shipped

- `final-model/predict.py` — predict callable
- `final-model/coeffs.json` — per-platform coefficients
- `final-model/manifest.json` — platform_support + predict_callable
- `out/fit.py` — reproducer for coeffs.json
