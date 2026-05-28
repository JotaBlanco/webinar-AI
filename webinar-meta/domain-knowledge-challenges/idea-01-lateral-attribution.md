---
title: Idea 01 — Lateral attribution
slug: idea-01-lateral-attribution
domain: vehicle-dynamics
tests:
  - attribution-discipline
  - regime-segmentation
  - operating-contract
  - metric-selection
  - truth-channel-discovery
best-fit-angles: [01-accretion, 04-author, 05-experiment]
weak-fit-angles: [02-empathy, 03-harness-as-product]

evaluation:
  spec: idea-01-lateral-attribution.canonical.yaml
  primary-kpis: [yaw_rate_rmse, cte_rmse]
  pool: held-out validation set (route-stratified, never seen by agents)

deliverable:
  directory: final-model/
  required:
    - predict.py
    - manifest.json
    - REPORT.md
  optional:
    - coeffs.json
    - any other artefacts the agent's predict() depends on
  predict-signature: |
    def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame:
        """Returns a DataFrame aligned with sim_df.index, with columns:
        - yaw_rate_pred_rads  (required, rad/s)
        - x_m, y_m            (optional, m) — if omitted, the grader integrates
                              them from the predicted yaw_rate using the
                              measured velocity.
        platform is one of FORD_MUSTANG_MACH_E_MK1, FORD_F_150_LIGHTNING_MK1.
        """
  failed-shape-policy: |
    If predict.py fails to import, raises, or returns an unusable shape, the
    cohort report marks the submission status="failed". No partial credit.

success-metrics:
  # Outcome KPIs — graded programmatically against the held-out val pool.
  # See evaluation.spec (canonical.yaml) for definitions.
  - id: yaw_rate_rmse-improvement-pct
    type: numeric
    rubric: improvement_pct on KPI 1 (yaw-rate RMSE) vs V0 baseline
    evidence: programmatic — grading skill computes this from predict.py
  - id: cte_rmse-improvement-pct
    type: numeric
    rubric: improvement_pct on KPI 2 (distance-resampled CTE RMSE) vs V0 baseline
    evidence: programmatic — grading skill computes this from predict.py
  # Hygiene rubric — assessed from REPORT.md.
  - id: regime-breakdown-present
    type: binary
    rubric: the report breaks out error by regime (straight / cornering / transient), not only an aggregate
    evidence-in-report: a per-regime table or chart of either KPI
  - id: methodology-consistent
    type: binary
    rubric: same segment list and same metric definition across every variant on the ladder
    evidence-in-report: variant table shares a fixed segment-set / regime-mask declaration in its header or caption
  - id: attribution-coherent
    type: numeric
    rubric: "|Σ marginal KPI drops − total drop| / total drop (no double-counting)"
    threshold: "< 0.15"
    evidence-in-report: marginal-improvement column and total-drop value both present and reconcilable
  - id: honest-regression-flagged
    type: binary
    rubric: any variant that worsened either KPI is reported as a regression with a physical reason; vacuous if no regression occurred
    evidence-in-report: variant table includes regression rows with a physical-cause column, OR an explicit "no regressions observed" statement
---

# Idea 01 — Lateral attribution

## The task prompt

```
We have a kinematic single-track vehicle dynamics model that takes measured
steering angle and velocity as inputs and predicts lateral behaviour — yaw
rate and the trajectory (x, y, heading) that follows from it.

Data lives at data/. The baseline (V0) is in code/ks_model.py; its predictions
are pre-computed as yaw_rate_pred_rads in every data/sim/segments/.../sim.csv,
alongside the measured truth channel (yaw_rate_meas_rads) for Ford platforms.

Improve the lateral fidelity of the model. You'll be graded on two primary KPIs:
  1. Yaw-rate RMSE (rad/s, lower is better)
  2. Distance-resampled cross-track-error RMSE (m, lower is better) —
     your trajectory vs the truth trajectory, sampled at uniform distance.

Ship your final model at final-model/:
  - predict.py exporting:
       predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame
       Returns a DataFrame aligned with sim_df.index, with columns:
         - yaw_rate_pred_rads (required, rad/s)
         - x_m, y_m (optional, m) — if omitted, the grader integrates them
           from your yaw_rate using the measured velocity.
  - manifest.json declaring platform_support and predict_callable
  - REPORT.md with your methodology
  - any coeffs / scripts your predict() depends on

The grader imports predict.py and applies your function to score the two KPIs.
If predict.py fails to import, raises, or returns an unusable shape, your
submission is marked failed.
```

Every agent of every module receives this prompt. Substrate (skills, tools, AGENTS.md, domain READMEs) is what differs across modules and angles. The prompt names the *task contract* (problem, metric, deliverable shape) — it does not name *methodology* (variant ladder, anti-patterns, platform-specific tricks).

## Why this is challenging in general

Even with the realistic prompt above, an agent without substrate support has to make the following calls on its own. The traps below are what the substrate of an M2+ module is supposed to cure.

| # | Trap | What goes wrong | Substrate cure | Visible artefact in M1 report |
|---|---|---|---|---|
| 1 | **Platform discovery** | Three platforms exist in `data/sim/segments/`; only Ford has a usable `yaw_rate_meas_rads` truth channel. Tesla has more segments and is tempting to default to; the prompt names Ford only in passing. | Truth-channel matrix per platform in AGENTS.md. | Agent fits/scores on Tesla, or fabricates a truth, or silently picks one Ford platform and ships for both. |
| 2 | **Operating contract** | Parts of the KS model state are clamped to measured values (`v`, `δ`), parts are predicted (`ψ̇`, `a_y`). "Fidelity on the clamped channel" is technically true and operationally meaningless. | One line in AGENTS.md naming what is clamped vs predicted. | Report praises a channel whose value is trivially right by clamping. |
| 3 | **Variant catalogue** | A weak agent proposes one big leap (KS → neural net) and reports aggregate improvement, losing attribution. A strong one proposes a fine-grained ladder. A *very* strong one recognises that some upgrades are illegitimate within the contract (e.g. unclamping). | Reference doc with bounded catalogue of legitimate upgrades. | Single-variant report, or a ladder mixing legitimate and contract-violating moves. |
| 4 | **Attribution discipline** | Marginal vs Shapley vs ablation — all valid, all producing different numbers. Running variants in series and crediting each with its own KPI drop double-counts when two upgrades close overlapping residual. | Skill enforcing fixed order with strict marginal accounting in the report table. | Marginal drops sum to more than the total drop. |
| 5 | **Two-KPI tradeoff** | A model that wins yaw-rate but loses CTE is biased (small persistent yaw-rate bias accumulates in trajectory); a model that wins CTE but loses yaw-rate is conservative. The report must show this tradeoff coherently, not pick the favourite KPI and ignore the other. | Substrate naming both KPIs as primary; diagnostic guidance on how mismatches reveal model character. | Report quotes only one KPI, or quotes both without acknowledging the tradeoff. |

These traps generalise. (1) shows up every time a data scientist runs a model against a dataset they didn't collect. (2) is the bug that takes down most production ML systems on the day a "trivial refactor" silently changes what the model is conditioning on. (3) is the vibe-shipping anti-pattern. (4) is the half-life of every aggregate metric reported in any ML paper. (5) is the metric-aggregation question that every benchmark with more than one number eventually faces.

The substrate's job is not to make the agent smarter; it's to make these failures **visible** and **avoidable**.

## Why it works for the workshop angles

For **01 accretion** — every trap maps one-to-one onto a substrate layer (see table). The audience reads M1's report, names the traps it hit, then watches M2's AGENTS.md grow the line that cures one, M3's skill add the procedure, M4's eval verify it.

For **04 author** — the substrate the domain expert writes *is* the contract clarification, the truth-channel matrix, and the variant catalogue. The expert seat turns the under-specified question into a sharp one in front of the audience.

For **05 experiment** — tests whether workflow / universal-agent / bespoke tiers each handle attribution differently. A workflow hardcodes the ladder, an agent with a skill adapts it, a bespoke agent proposes a new rung.

Weaker fit for **02 empathy** (per-turn token cost isn't the centrepiece here) and **03 harness-as-product** (no six-component spine is naturally visible).

## Predicted M1 vs M4 spread

- **M1** — gets the realistic prompt and nothing else. Likely to default to one Ford platform without testing the other (the prompt mentions Ford in passing but doesn't enforce both). Likely to write a single-variant predict.py with no attribution ladder. Likely to optimise yaw-rate RMSE and lose CTE because the bias accumulates. The submission is parseable and gradeable (the deliverable contract guarantees that) but the report is thin and the model's tradeoffs are unconscious.
- **M2** — fixes the platform-coverage and clamping questions via the truth-channel matrix and operating-contract section in AGENTS.md. Still trips on attribution discipline (variant ladder under-specified, no formal marginal accounting). Numbers are real; methodology is fuzzy.
- **M3** — ladder grounded in the catalogue. Attribution is honest. May report unflattering findings (a canonical upgrade making things worse on one KPI) with a physical reason. This is the "skill makes the agent more honest, not more optimistic" beat.
- **M4** — most disciplined, plan-then-execute, both KPIs reported with their tradeoff acknowledged. The eval (canonical KPIs on the held-out val pool) is what differentiates a defensible submission from a careless one.

The spread is *categorical*, not just *quantitative*: M1 may pass one KPI and fail the other; M4 should optimise both with full attribution.

## Iteration log

- **2026-05-26 — webinar-angle-A, iter 1.** Used an earlier, leakier variant of the prompt that named "speed-known mode" and "yaw rate." Hardened to a deliberately-naked version after retro (see `webinar-angle-A/_observations/`). The leakier prompt was retained as the comparison case: even with the hint, M1 still tripped traps 2/3 in iter 1.

- **2026-05-27 — full cohort grading on 85 agents (run `20260527-164838`).** Naked-prompt purity cost the cohort: agents picked different metrics, fit on different slices, shipped inconsistent output shapes. Canonical comparison required a per-agent judge subagent that reconstructed models from REPORT.md prose — non-trivial failure rate. See `deprecated/raw-model/idea-01/_grade/.../scaffolding-analysis.pdf` for the post-mortem.

- **2026-05-28 — switched to realistic-prompt + deliverable contract.** Prompt now names the metrics, data location, code location, and required output shape (callable `predict.py` at `final-model/`). Substrate still owns methodology (variant catalogue, anti-patterns, train/dev split discipline) — the prompt names the *contract*, not the *recipe*. The `naked-prompt-audit` block has been dropped from the frontmatter; replaced by `evaluation:` and `deliverable:` blocks declaring how submissions are graded. The grading skill (`webinar-meta/skills/grade-cohort-reports`) now imports `final-model/predict.py` directly instead of reconstructing models, which collapses N judge subagents into a single deterministic eval loop.
