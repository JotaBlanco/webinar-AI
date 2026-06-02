# REPORT — module-3.v3-agent-07

## Headline (pooled, full dev set)

| metric | V1 | shipped (v1-asym-debias) | Δ vs V1 |
|---|---|---|---|
| yaw_rate_rmse (rad/s) | 0.005874 | **0.005805** | **−1.2%** |
| cte_rmse (m)          | 56.807   | **54.689**   | **−3.7%** |

Per-platform deltas (Mach-E was V1's worst):

| platform | yaw V1 → cand | cte V1 → cand | cte_drift V1 → cand |
|---|---|---|---|
| Lightning | 0.00566 → 0.00564 | 62.19 → 61.95 | +0.32 → −0.67 |
| Mach-E    | 0.00859 → 0.00841 | 98.68 → **92.49** | −21.98 → **−4.88** |
| IONIQ-5   | 0.00766 → 0.00760 | 69.53 → 67.65 | −11.57 → −6.17 |
| Tesla     | 0 → 0 (passthrough) | 0 → 0 | 0 → 0 |

All bias-warning 🚨 cleared.

## V1 residual diagnosis (what I attacked)

Per-regime slice of V1 residuals on Mach-E showed a strong **left/right
asymmetry**: turning-right bias −0.0072 vs turning-left −0.0003. Same shape on
IONIQ-5 (−0.0055 vs +0.0003). V1's single scalar `g` and symmetric `δ₀` cannot
fix this — it's a sign-dependent steering response. Lightning was symmetric;
Tesla has no truth so can't be fit.

## Candidates built (full registry in MODELS.md)

1. **v1-steerrate-ff** *(structure: differs-from-V1, shelved)* — V1 + `k_dd · d(δ)/dt`
   feedforward. Targeted the transient-regime residual. <1% improvement, k_dd sign
   flipped negative on Mach-E (np.gradient phase artefact, not real lag). The
   transient residual needs an actual second-order dynamic, not a scalar
   input-derivative.

2. **v1-asym-gain** *(structure: differs-from-V1, assessed)* — V1 with smooth-blended
   `(g_left, g_right)` replacing the single `g`. Fitted per platform via
   Nelder-Mead. Pooled: −0.5% yaw, −1.4% CTE. Mach-E bias fraction 0.03 → 0.004.

3. **v1-asym-debias** *(structure: differs-from-V1, SHIPPED)* — adds a gated additive
   output bias `b_offset · 1[v>2]` on top of #2. Zeroed on Lightning (already at
   bias-threshold), halved on Mach-E/IONIQ-5 (guard against the 80-seg subset
   overfit that flipped Lightning bias in joint-fit attempts). Final ship.

## Negative results worth flagging

- **The b_offset fit overfits subsets.** Joint Nelder-Mead on 80 segments
  produced a Lightning `b_offset = −0.00165`. On the full 175-seg Lightning set
  that *flipped* signed bias from +0.00012 to −0.00169 and degraded CTE to 68 m.
  Mitigation: don't fit additive offsets where the V1 signed bias is already
  within ⚠️ threshold. Documented in `EXPERIMENTS.md` E04a and in
  `references/dynamics-formulations.md` under "Rung 0.5".
- **Steer-rate feedforward is the wrong attack on the transient residual.**
  The negative k_dd on Mach-E confirms it.

## Painful absence in this harness

The biggest cost was **the absence of a `fit-model` skill that takes a
predict_factory and returns coefficients + diagnostics directly.** I ended up
hand-rolling per-candidate fitters (`out/fit_asym.py`, `fit_asym2.py`,
`fit_asym3.py`, `fit_asym_debias.py`) and burned my first attempt on a 25×25
grid scan with a Python for-loop integrator that didn't finish in 5 minutes
before I killed it and rewrote with `scipy.optimize.minimize`. AGENTS.md listed
`fit-model/` in the skills inventory but it is not present in `skills/`. The
diagnostic skills (`score-model`, etc.) are excellent — the fitting machinery
is the hole.

## Rules I noticed myself about to break

- I started to load `data/sim/segments/.../sim.csv` *inside* my predict() to
  read per-segment truth statistics. Caught it before writing — that's a
  textbook denied-column slip and would have silently failed at canonical
  grading time. AGENTS.md's "operating contract" section was load-bearing here.
- I almost validated my fit by reading another agent's `final-model/REPORT.md`
  to compare scores. The isolation rules stopped me — and rightly.

## Most surprising thing learned

**V1's residual is not symmetric on cars one would expect to be symmetric.**
A 7× factor between turning-right and turning-left signed bias on a 2-year-old
EV is jarring — could be a steering-column sensor zero, a suspension geometry,
or a route-distribution artefact in the dev set. I leaned "route-distribution
is plausible" but couldn't verify (no L/R-balanced subset trivially available),
so the model fixes a *symptom* whose generality is unverified. The honest
preflight warn ("max |Δyaw| = 0.000378 rad/s on Lightning < 0.001 tolerance")
is exactly right: the structural change is in the *signed-bias* subspace, not
the noise variance — and noise variance dominates RMSE. The 1.2% pooled yaw
win is a bias-fraction reduction that materialises as ~4% on CTE because
CTE is a double-integral of bias.

## Files

- `final-model/predict.py`, `coeffs.json`, `manifest.json`, `REPORT.md`
- `models/v1-asym-debias/` (shipped); `models/v1-asym-gain/`; `models/v1-steerrate-ff/`
- `MODELS.md`, `EXPERIMENTS.md`, `references/dynamics-formulations.md` (appended)
- `out/fit_asym3.py`, `fit_asym_debias.py` (the fitters that worked)

Preflight: PASSES (1 warn on structural-novelty for Lightning, documented).
