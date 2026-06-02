# Phase 2 — Plan — seed prompt

Paste this into a fresh Claude Code session at the template root (or pass it
via `claude --append-system-prompt` — `phases/2-plan/run.sh` does this for
you when the CLI is available).

---

You are entering **Phase 2 (Plan)** of an RPI-first m4 template.

Before doing anything else, read:

1. `phases/2-plan/README.md` — your guide for this phase.
2. `phases/1-research/artifacts/RESEARCH.md` — the locked Phase 1 artifact.
   This is your primary input.

Then, **only if** RESEARCH.md's `## References cited` section names a
reference whose body you actually need to interpret a candidate, you may
load that specific reference. You may not load references not in that list.
The cited-by-name rule is what makes the recovery path possible without
turning Plan into Research again.

Your single output is `phases/2-plan/artifacts/PLAN.md` (skeleton written
by `run.sh`).

**Scope hard limits for this session:**
- Do **not** read references NOT named in RESEARCH.md's `## References cited`.
- Do **not** read `code/v1_baseline.py` or any `models/<*>/predict.py`.
- Do **not** edit `MODELS.md` / `TREE.json` / `EXPERIMENTS.md`.
- Do **not** write code.
- You may inspect `skills/*/SKILL.md` frontmatter for routing decisions.
- Keep context fill below 40%.

**The candidates rule:** default 2 candidates — one rung-0 refinement +
one structurally-different. Up to 3 only if RESEARCH.md surfaces two
genuinely distinct structural candidates that would each weaken the other
slot in the default pair; document the rationale in PLAN.md's
`## Why three candidates` section.

**Orthogonal (residual learner) is a peer of rung-1+, not a fallback.**
The cohort-evidenced winning pair is `(rung-0 bias correction) +
(orthogonal residual learner)` (§2 + §4). If you choose rung-1 over
orthogonal as the structurally-different candidate, document the
residual-character rationale in PLAN.md's `why this rung over the
alternative` field.

## EXIT RITUAL — DO NOT SKIP

When `PLAN.md` is complete, run **both** commands, in order:

```
bash lock.sh phases/2-plan/artifacts/PLAN.md   # LOCK — required
exit                                            # close THIS session
```

The lock is the gate that protects Phase 3's fresh-context bet — Phase 3's
`run.sh` REFUSES to start if PLAN.md is still writable, and
`pre-flight-final-model` rejects the final bundle if PLAN.md was edited
during implementation. Forgetting the lock is the single most common way
the RPI discipline silently weakens.

Do not invoke Phase 3 from this session — start Phase 3 fresh.
