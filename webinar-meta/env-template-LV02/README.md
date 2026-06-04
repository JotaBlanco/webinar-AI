---
title: webinar-00-template-m2.v3 — Module 2 starter substrate (skills toolkit, v3)
summary: Module 2 v3 template for the lateral-fidelity webinar. Ships with ten small, modifiable skills plus a shared math library. The v3 changes target the bottlenecks the m2.v2 cohort surfaced — fit warnings + train/dev gap inline (overfit visibility), route-bias diagnostic (per-route opportunity ranking against observable features), a 2-D residual heatmap mode, and a residual-structure verdict skill that tells the agent whether they're at the noise floor or there's a specific term left to add. Loop discipline updated to "don't ship V1".
tags: [template, webinar, m2, m2v3, skills, lateral-fidelity]
updated: 2026-06-01
---

# webinar-00-template-m2.v3

Module 2 substrate for the lateral-fidelity webinar. Skills are designed to **widen exploration** rather than funnel every agent to the same answer.

This README is for the human setting up the template. The agent reads [AGENTS.md](AGENTS.md) — that's the authoritative source for the working-directory layout, the skills inventory, and the modify-the-skill protocol. Don't duplicate that content here.

## What changed in v3

Informed by the m2.v2 cohort grade at `_grade/20260601-002255/`. v2 won on CTE mean (+1.7pp) and σ (1.9 vs 2.7) over v1; v3 targets the new bottleneck the v2 reports identified — overfit visibility, route-level residual that the platform fit cannot reach, and 1-D residual plots that fold two-axis structure into noise.

1. **fit-model warnings + train/dev gap inline.** `fit()` now returns a `warnings` dict per platform (`co_collapse`, `stuck_on_bound`, `wide_train_dev_gap`, `did_not_converge`) and a `gap`/`gap_fraction` dict. `format_fit_summary()` opens with the warnings block and the per-platform table has `dev_obj`, `gap`, and `gap_%` inline-flagged. v2 agents kept hand-rolling a train/dev wrapper to spot overfit (≈10 min each) and one even rode an identifiability cliff (`gain × L_eff` both free → both went to 0.003 and the loss improved). The warnings catch this without the agent having to look for it.
2. **New `route-bias/` skill.** Per-route signed yaw bias and signed CTE drift, ranked by *share of the platform's pooled error* — not just by RMSE — so the agent sees opportunity, not just noise. Includes per-route means of input features so the agent can correlate bias against an OBSERVABLE feature. Diagnostic only — route ID is not an inference input, so the skill explicitly tells the agent to find an input feature to add to their model rather than apply a route-keyed correction.
3. **`inspect-residuals` 2-D heatmap mode.** `inspect_residuals_2d(predict_fn, x_feature, y_feature)` returns a per-platform mean-residual heatmap on (x, y) with a diverging colour scale so signed bias jumps out. v2 agents asked for this explicitly — understeer is `v² × delta`, so a 1-D plot folds one axis into noise. Now schema-aware too (the 1-D mode was silently dropping Tesla; that's gone).
4. **New `residual-structure/` skill + "don't ship V1" loop discipline.** This is the v3 answer to the v2 yaw-RMSE ceiling. Almost every v2 agent stopped at V1 understeer; the one who beat them by 9% saw that the V1 residual was autocorrelated (sensor-pipeline delay) and added a steering-rate `τ·d(δ)/dt` lead term. `residual-structure` exposes that signal directly: per platform, it returns a verdict — `noise_floor` (stop) or `structure_detected` with a specific reason ("residual autocorrelated at lag 6 → add a τ·d(δ)/dt term"). AGENTS.md gains a "Don't ship V1" section that names the failure mode and prescribes the V1 → diagnose → V2 → compare → ship loop.

## Design principles (unchanged from v2)

1. **Diagnostic surface, not polished oracle.** `scoring-model` returns per-segment tables, per-platform signed bias, bias-vs-noise decomposition, per-route pooling, worst-N outliers, distributions, plus a `format_summary` dashboard — not a single pooled number. The summary opens with a **signed-bias check** because the M2-cohort under-performed on CTE specifically: CTE is bias-dominated and agents kept tuning yaw-RMSE noise.
2. **Schema-aware skills.** `scoring-model`, `fitting-model`, `inspecting-residuals`, `route-bias`, and `residual-structure` share a single `PLATFORM_SCHEMA` that maps each platform to its truth column and V0 baseline column, so platforms whose sim.csv uses a non-default schema (e.g. Tesla's `psi_dot_rads`) score and fit cleanly. Earlier versions silently dropped any platform missing `yaw_rate_meas_rads`.
3. **Observation AND fit AND post-fit diagnostics AND "is there more?".** v1 had only observation. v2 added a model-agnostic fitter. v3 closes the loop with overfit visibility (fit warnings + train/dev gap), per-route opportunity ranking, a 2-D residual heatmap mode, and a per-platform verdict on whether the residual is at the noise floor or there's a specific term left to add. The point isn't to push the optimiser harder — it's to tell the agent when their V1 has more headroom and what shape the missing term has.
4. **Skills as clay, not library.** SKILL.md prose pushes hard on "edit the body if the output isn't useful". Skills are short on purpose.
5. **No domain-knowledge references in M2.** Anti-patterns / approach menus / KPI-tradeoff docs are held for Module 3+ on purpose.

## How to drive Module 2 with this template

1. Symlink `data/` (whole repo data tree) and `code/` (whole repo code tree) into each agent's working dir — see [data/README.md](data/README.md) and [code/README.md](code/README.md).
2. Open the agent dir in Claude Code. `AGENTS.md` loads.
3. The agent's task prompt names the two KPIs to minimise.
4. The agent inspects skill metadata first (cheap), loads bodies on demand.
5. Iterate: `score-model` (read the signed-bias check at the top) → `fit-model` (pass `bounds` and `dev_segments`; read the warnings block) → `residual-structure` (verdict tells you whether to stop or what term to add) → if structure remains, `route-bias` and/or `inspect-residuals` (1-D or 2-D) for the specific feature → modify model, refit. `compare-models` for A/B between V1 and V2. `pre-flight-final-model` before declaring done. **Don't ship V1 without running residual-structure first.**

## What's *not* here (held for later modules)

- No `references/` directory with domain knowledge (per-segment derivations, anti-patterns, KPI tradeoffs). These live in Module 3+.
- No `tasks/` directory. The KPI brief lives in the agent's run-time prompt, not in the template.
- No `evals/` directory. Skill-level evals appear in later modules.
- No `tools/` or `.mcp/`. Empty in M2; if the project gains MCP servers later, add them then.

## Dependencies

- Python 3.11+
- `uv` for env management (`uv sync` after first clone)
- Claude Code
