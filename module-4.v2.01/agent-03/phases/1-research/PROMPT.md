# Phase 1 — Research — seed prompt

Paste this into a fresh Claude Code session at the template root.

---

You are entering **Phase 1 (Research)** of an RPI-first m4 template.

Before doing anything else, read:

1. `phases/1-research/README.md` — your guide for this phase. Authoritative.
2. `AGENTS.md` (root) — operating contract only (8-column input, denied
   columns, V1 floor). Treat it as a contract reference, not a guide.

Your single output is `phases/1-research/artifacts/RESEARCH.md` (skeleton
already exists). Fill it in.

**Scope hard limits for this session:**
- No code. No `models/` directories. No edits to `MODELS.md` / `TREE.json` /
  `EXPERIMENTS.md`.
- You may run `skills/score-model` and `skills/residual-structure` on V1 to
  characterize V1's residual. You may NOT score new candidates.
- Keep context fill below 40%. Load only the references the phase README
  names as required.

Your output target: `RESEARCH.md` with ≥5 candidates (≥3 structurally
distinct from V1), cohort findings cited by section number.

## EXIT RITUAL — DO NOT SKIP

When `RESEARCH.md` is complete, run **both** commands, in order:

```
bash lock.sh phases/1-research/artifacts/RESEARCH.md   # LOCK — required
exit                                                    # close THIS session
```

The lock is the gate that protects Phase 2's fresh-context bet — Phase 2's
`run.sh` REFUSES to start if RESEARCH.md is still writable. Forgetting the
lock is the single most common way the RPI discipline silently weakens.
If you started Phase 2 in the same terminal and it errored, scroll up — the
error tells you to lock first.

Do not invoke Phase 2 from this session — start Phase 2 fresh.
