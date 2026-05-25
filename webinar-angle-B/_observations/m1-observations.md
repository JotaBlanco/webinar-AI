# M1 — observations

## Run summary
- Duration: ~4.4 min (261s)
- Total tokens: ~50k
- Tool uses: 18
- REPORT.md: written
- Isolation: respected (agent explicitly confirms no out-of-allow-list reads)

## What worked
- Baseline computed cleanly from the 4 existing sim CSVs (no regeneration needed).
- Proposed 6 improvements (more than the 3 asked for).
- Implemented 4 variants: bias correction, linear single-track, both combined, closed-form wheelbase refit.
- Honest ablation table including the wheelbase refit which **made things worse** (+126% on Mach-E, +121% on F-150).
- Best result: F-150 linST + bias gave **−47% RMSE ψ̇** (1.06 → 0.57 °/s).
- Generalisation honesty: explicitly flagged Mach-E bias does NOT generalise across segments.

## What slowed the agent down (per agent's own report)
1. **n=2 segments per platform** makes bias-generalisability question unanswerable. Wished for 5-10+ segments per platform with a pre-baked manifest.
2. **Missing `models.md` / `vehicle-mach-e.md` docs** — `ks_model.py` references `../models.md § "Speed-known framing"`, `parameters.py` references `../vehicle-mach-e.md`. These live OUTSIDE the allow-list (in KB002/KB003). Agent specifically wanted documented sign convention and any compensation applied to `BrakeSnData_3.VehLatComp_A_Actl`.
3. **Missing CAN-decode deps** (cantools/pycapnp/zstandard) blocked anything that needs `generate_simdata_ford.py` to regenerate — e.g. δ lag filter, transient ST with β̇, online bias estimator.

## My observations as orchestrator

- The agent did NOT seem actively impaired by the AGENTS.md bloat in this short single-turn run. ~50k tokens total — well below any context-fill cliff. The "computer in the dark" effect is much less visible in a one-shot run than in a multi-turn live session where the AGENTS.md gets reloaded *every turn*. **This is an important limitation of the experiment**: the 944-vs-53 lesson is about per-turn cost, and a 18-tool-use run doesn't pay it 100+ times like a real workshop session would.
- Despite the bloated, generic AGENTS.md, the agent succeeded at locating `ks_model.py` and `parameters.py` (presumably by `ls` / `grep`) and figured out the workflow from the code itself. This says something interesting: a competent agent can route around bad substrate by reading the code, but the *cost* (in tool uses, in tokens, in time) is what the inspector would surface in a real demo.
- The lack of signal-definition docs (the `../models.md` / `../vehicle-mach-e.md` references) bit the agent on a *physics interpretation* question — they couldn't decide if the F-150 a_y bias was a sensor-compensation artefact. This is exactly the kind of pain a domain-knowledge skill (NC-12 progressive disclosure) addresses cleanly. **M3 should fix this** because the `vehicle-dynamics-rlog` skill carries the conventions and the `sim-real-runtime` skill names the truth-channel sources.
- The wheelbase refit failure is interesting workshop fodder — the "obvious" calibration improvement that fails because of numerical conditioning in highway data. Worth quoting.

## Hypothesis for what M3/M4 might do better
- M3 agent has the skills; should propose the linST path more cleanly (it's *already named* in `vehicle-dynamics-rlog/SKILL.md`).
- M4 agent should NOT do the wheelbase refit at all (the plan phase would catch it as low-value).
- Both should land near or beyond F-150's −47% improvement.

## Open follow-ups
- The deps issue (cantools missing) is real and limits ALL modules equally. Consider installing them or providing a pre-regenerated larger segments manifest. Not a substrate problem — an environment one.
