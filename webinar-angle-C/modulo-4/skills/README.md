# skills/ — Modularity component (6)

Three skills, loaded metadata-first (the agent reads each `SKILL.md`'s frontmatter to decide whether to pull the body).

- `baseline-residual/` — compute baseline RMSE per Ford platform.
- `ablation-study/` — run an additive ablation across variants.
- `yaw-bias-correction/` — concrete domain skill: constant-bias correction. The simplest plausible improvement; use as variant A.

If you find yourself doing the same thing twice while solving the challenge, that's the signal to crystallise a new skill: walk the workflow once → write SKILL.md + helper script → re-run on a new instance → patch if it fails. See `AGENTS.md` for the universal-agent + skills sequencing rule.
