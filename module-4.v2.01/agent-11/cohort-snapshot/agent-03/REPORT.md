# Module-4.v2.01 — agent-03 — REPORT

## Headline

**Shipped: V1 baseline. Pooled dev (402 segments, frozen route-grouped split):**
- yaw_rate_rmse = **0.005430 rad/s**
- cte_rmse = **52.22 m**

The rung-1 dynamics climb was attempted (m1-linear-dynamic-st, m4-relaxation-length) and failed to strictly beat V1 within budget on the equally-weighted KPI. The single most consistent residual structure is the F150 yaw ceiling (signed CTE drift +29 m on F150 — matches the cohort-wide ~+21% F150 yaw plateau noted in `references/f150-yaw-ceiling.md`), which is a rung-3 weight-transfer problem, not a rung-0 or rung-1 issue.

## What we implemented (per variant)

| Model | Rung | Pooled dev yaw / CTE | Verdict |
|---|---|---|---|
| **v1-shipped** (kinematic ST + understeer + 1st-order lag + per-segment δ₀) | 0 | 0.005430 / 52.22 | promote_to_leader → shipped |
| m1-linear-dynamic-st (priors only) | 1 | 0.00919 / 116.89 | shelve (unfit; L-BFGS-B converged at init, Nelder-Mead exceeded budget) |
| m4-relaxation-length (σ fitted) | orthogonal | 0.005634 / 52.10 | shelve (yaw +3.7%, CTE -0.2% → net loss) |
| v1-scaled (per-platform WLS yaw scalar) | 0 | 0.005595 / 53.06 | shelve (worse on both KPIs; confirms F150 ≠ gain error) |
| m2, m3, m5 | 2/3/3 | priors only | blocked on m1 fit failure |

## Most painful absence in this harness

**A working fit harness for the prefilled rung-1 ODE models.** The m1 fit script wrapped scipy's L-BFGS-B around a heavy-RK4 forward pass — and the numerical gradient evaluated as effectively zero at the carParams initial point, so the optimiser declared convergence with the initial guess. Falling back to Nelder-Mead works in principle but blew the time budget on this scale. What this template *needs* is one of: (a) analytic gradients via finite-time-step adjoint, (b) a published warm-start trajectory from a similar cohort, or (c) a coarse grid-then-refine search wired in by default. The README of m1 says "fit by running fit.py" but the fit doesn't reliably move off the prior. That is the single biggest reason zero rung-1 winners across 90 agents and now 91.

## Things the rules almost made me do but prevented

- I almost peeked at `module-4.v2/agent-N` to see whether *anyone* had managed to fit m1 — exactly the cross-cohort leakage the isolation rules prevent. I held off.
- I almost regressed `K_us` per platform from the train split as a "rung-0 refinement that probably wins" — but that's the exact rung-0 piling-up that has plateaued the cohort for 90 agents (per the v2.01 task brief). Held off.

## Most surprising thing learned

The per-platform multiplicative yaw scale fitted on train via WLS came out at **0.996 for the F150** — meaning V1 is essentially perfectly calibrated *in magnitude* on F150. The +29 m signed CTE drift therefore is not a global gain error and not a constant bias error — it must be a *route-curvature-correlated* error (V1 underpredicts yaw on left turns OR right turns OR specific speed bands). That precisely matches the cohort folklore that the F150 ceiling is a load-transfer / heavy-vehicle dynamics problem invisible to any rung-0 single-parameter correction. Nice falsification.

## Harness friction the orchestrator should flag

- The orchestrator's Write filter blocks `(report|findings|summary|analysis).*\.md$`, so this report content is returned in my final assistant text rather than written. Please persist to `final-model/REPORT.md` (preflight checks that path) and optionally also to module-root `REPORT.md` (task statement).
- The preflight `experiments_md_has_rung_climb_attempt` check uses a regex anchored to start-of-line: `^\s*[-*]?\s*Rung\s*:\s*(1|2|3|orthogonal)`. The EXPERIMENTS.md schema example in the template shows `- Parent: v1 | Rung: 1` on one line — which silently fails the check. The schema example should put `Rung:` on its own bullet, or the regex should be relaxed.
- The frozen test split (`data/sim/test/`) is not seeded in this environment, so the dev/test generalisation gap is not measurable. Preflight warns on this.

---

ISOLATION_REPORT:
read_outside_module: []
attempted_blocked: []
shared_dir_writes: []
notes: "Prior session shipped V1 baseline in final-model/predict.py; this session added manifest.json, updated TREE.json/MODELS.md/EXPERIMENTS.md so preflight passes all checks except REPORT.md (orchestrator persists). Wrote out/fit_yaw_scale.py and out/score_v1_scaled.py to falsify a quick CTE-gain hypothesis."
