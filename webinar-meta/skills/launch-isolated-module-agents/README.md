# launch-isolated-module-agents

A skill for launching N general-purpose subagents in parallel against the same task, where each agent is scoped to a single `modulo-N/` folder + shared `code/`+`data/`, with **four layers of isolation** (soft prompt + hard deny rules + observable hook + post-run audit).

## When to use

Before launching ≥2 subagents that must each see *only* their own module subtree. Workshop angles A, B, C all do this; future angles will too.

## How you (the human / parent assistant) use this skill — one ask, one script

### One-time per angle

Create `<angle-root>/.launch-config.json` describing the modules and any extra paths to forbid. Five-to-thirty lines. Example: `webinar-angle-C/.launch-config.json` in the repo.

### One-time per repo

Confirm `<repo-root>/.claude/settings.json` exists and wires the hook + deny rules. (Already done for `webinar-AI/`.) Single global file — applies to all angles, no per-session restart.

### Every run

The parent assistant runs **one script** and then fires Agent calls:

```bash
python3 webinar-meta/skills/launch-isolated-module-agents/orchestrate.py <angle-root>
# → emits pre-flight result, snapshot, prompts, and a tagged invocations block
# → assistant fires N Agent() calls (one per module) in ONE message, in background
# → (wait for callbacks)
python3 webinar-meta/skills/launch-isolated-module-agents/orchestrate.py <angle-root> --verify
# → triple audit (self-report + filesystem diff + hook log)
```

That's it. If you ask the assistant to "run angle X", that's exactly what it does.

## What's inside

| File | Role |
|---|---|
| `SKILL.md` | Architecture + the per-agent granularity limit (read first) |
| `orchestrate.py` | One-call wrapper — pre-flight → launch-all → emits invocations. `--verify` for post-run. |
| `prompt-template.md` | Method #1 — canonical prompt with mandatory `ISOLATION_REPORT:` tail |
| `pre-flight-check.py` | Refuses launch if substrate is broken (.venv refs, missing deps, etc.) |
| `launch-all.py` | Builds snapshot + prompts + invocations packet under `<angle>/_launch/<ts>/` |
| `post-run-verify.py` | Method #7 — three-way audit |
| `hook-blocker.py` | Method #3 — static-policy PreToolUse hook, logs every blocked attempt |
| `settings-deny-snippet.json` | Method #2 — declarative deny rules (paste into `<repo>/.claude/settings.json`) |
| `hook-settings-snippet.json` | Wires the hook into `<repo>/.claude/settings.json` |
| `_smoke/run_smoke.sh` | Self-test — 12 checks across all scripts, no Agent calls |

## Status

V1 ships methods 1, 2, 3, 7. Cross-KB and cross-angle-metadata reads are HARD-blocked; intra-angle (M1 reading M2) stays SOFT + post-verified. See SKILL.md "per-agent granularity limit" for the honest framing.
