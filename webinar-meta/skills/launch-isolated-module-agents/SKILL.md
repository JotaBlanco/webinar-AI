---
name: launch-isolated-module-agents
description: Launch N general-purpose subagents in parallel against the same task, where each agent is scoped to a single `modulo-N/` folder plus the shared `code/` and `data/` symlinks, and nothing else. Combines four isolation layers — prompt (soft), settings.json deny rules (hard, native), pre-tool hook (hard, observable), and post-run verification (detective) — so the workshop comparison is auditable, not just claimed.
when-to-load: Before launching ≥2 subagents that must each see *only* their own module subtree plus shared runtime. Load the skill body before invoking the Agent tool; the body contains the four-layer setup and the scripts that make it reliable.
inputs: A manifest (JSON) of `{module_name, module_path, harness_components_present, task_relative_path, time_budget_minutes}` per agent.
outputs: One subagent invocation per module; a `_launch/` folder under the angle root with materialised prompts, pre-flight reports, blocked-attempts log, and post-run verification.
load-cost: ~300 tokens metadata, ~1400 tokens body.
---

# launch-isolated-module-agents

## Why this skill exists — honest version

Three webinar angles (A, B, C) have previously launched module agents using **prompt-level soft whitelisting only**. In all three the orchestrator reported "no out-of-scope reads" — but **none of the runs had an audit trail to back the claim**. Angle C had one agent self-reporting a near-miss it caught itself ("I almost ran `find` from the root"). The actual violation rate is unknown, because nothing was watching.

That isn't good enough for a workshop where the cross-module comparison *is* the deliverable: if even one of the four agents glanced at a sibling module or a design KB and silently parroted "the right answer", the comparison is contaminated and we'd never know.

This skill adds three more layers so the question "did isolation hold?" has an objective answer:

| Layer | Method | Strength | What it protects |
|---|---|---|---|
| 1 | Prompt-level whitelist | Soft | Everything (intent only) |
| 2 | `settings.json` `permissions.deny` | Hard, declarative, native | Cross-KB and cross-angle reads |
| 3 | `PreToolUse` hook with logging | Hard, observable | Same as #2 + logs every blocked attempt |
| 7 | Post-run verification (3-way) | Detective | Triangulates self-report + filesystem diff + hook log |

## The per-agent granularity limit — read this carefully

`settings.json` and `PreToolUse` hooks are **per-project**, not per-subagent. Subagents inherit the parent session's settings; you cannot give M1's subagent a different deny list than M4's via native Claude Code config. Therefore:

- **Cross-KB and cross-angle isolation is HARD-enforced** by layers 2 and 3 (good — this is the disaster scenario, where an agent reads the design KB and parrots the "right answer").
- **Intra-angle isolation** (M1's agent reading `modulo-2/`) **remains SOFT** (prompt-only). Layer 7 catches violations after the fact.

The honest framing: *"hard outer ring, soft inner ring, detective audit on both."* If you need hard intra-angle enforcement, use `container-use` (future work) or per-agent OS sandboxes — neither is in V1.

## Architecture — the four artifacts and how they compose

1. **[`prompt-template.md`](prompt-template.md)** — canonical prompt, placeholders for module path, components-present list, task path, time budget. The prompt ends with a mandatory `ISOLATION_REPORT:` block the agent must fill — this is what post-run-verify parses for self-reported reads.

2. **[`settings-deny-snippet.json`](settings-deny-snippet.json)** — paste-into-`<angle>/.claude/settings.json`. Denies `Read(...)` and `Bash(...)` patterns matching cross-KB and cross-angle paths. Resolved at session start; subagents inherit.

3. **[`hook-blocker.py`](hook-blocker.py)** + **[`hook-settings-snippet.json`](hook-settings-snippet.json)** — same coverage as #2 but executed as a `PreToolUse` hook. Two extras the deny rules cannot do: (a) symlink-aware path resolution (catches an agent reading via a re-symlink), (b) appends every blocked attempt to `<angle>/_launch/blocked-attempts.log` for post-run audit.

4. **[`post-run-verify.py`](post-run-verify.py)** — three-way audit per module:
   - Parses the agent's `ISOLATION_REPORT:` self-report block. Flags any path not under `module_path | code | data`.
   - Diffs `code/` and `data/` against a pre-launch snapshot (`<angle>/_launch/<timestamp>/snapshot.txt`). Any new or modified file is a violation (shared dirs are read-only by contract).
   - Reads `<angle>/_launch/blocked-attempts.log` and reports counts per agent (which the hook tagged with a session marker — see hook script).

   Cross-checks the three views. Any disagreement (e.g. agent self-reports clean but hook logged blocks for it) is loud.

5. **[`pre-flight-check.py`](pre-flight-check.py)** — sanity checks for *every recurring substrate bug we've hit*:
   - Symlinks `code` and `data` resolve to expected absolute paths.
   - `python3 -c "import pandas, numpy"` works from the module dir.
   - `AGENTS.md` doesn't reference a `.venv` that doesn't exist (angle A's B1 bug).
   - Test-writes a dummy `REPORT.md` to the module — reveals whether the sub-agent harness's `.md`-write block applies (angles B and C all hit this).
   - Greps the rendered prompt for any absolute path that doesn't exist on disk (catches typos in forbidden-list paths).

6. **[`launch-all.py`](launch-all.py)** — reference orchestrator. Reads the manifest, runs pre-flight, materialises prompts, snapshots `code/` and `data/`, prints the Agent tool invocations as JSON the parent assistant should paste (the orchestrator can't itself call the Agent tool — only the parent assistant can).

## Procedure (the one-call flow)

### Setup — done once for this repo

`<repo-root>/.claude/settings.json` exists and wires the hook + deny rules. Already in place for `webinar-AI/`. Single global file; no per-session restart needed; the hook activates for every Claude Code session rooted anywhere under the repo.

### The shared `data/` topology (as of 2026-05-31)

`<repo-root>/data/` is three symlinks (not a real tree):

```
data/
├── raw/        → KB_PARENT/KB003/data/raw                  (raw rlogs)
├── sim-only/   → KB_PARENT/KB003/data/sim-only/segments    (input-only mirror — operating-contract surface)
└── sim-full/   → KB_PARENT/KB003/data/sim/segments         (full schema including truth — training/scoring only)
```

`sim-only/` is what the canonical grader hands to each agent's `predict()`; truth columns aren't in those CSVs. `sim-full/` is for training and local scoring. The agent prompt template documents this for each agent.

**Caveat for the `KB_PARENT/KB003/**` declarative deny rule**: the data/ symlinks resolve into KB003. Depending on whether `permissions.deny` matches the literal path argument (safe) or the post-symlink-resolution path (would break legitimate `data/` reads), the KB003 deny may need to be removed. See `_note_on_KB003_symlink_collision` in `settings-deny-snippet.json` for the smoke test. The symlink-aware hook (layer 3) is still the catch-all for direct KB003 reads via absolute path.

### Setup — done once per angle

Write `<angle-root>/.launch-config.json` (5-30 lines). Schema:

```json
{
  "angle_name": "webinar-angle-C",
  "extra_forbidden": [
    "/abs/path/to/F1/KB001",
    "/abs/path/to/F1/KB002"
  ],
  "modules": [
    {
      "module_name": "modulo-1",
      "module_path": "/abs/path/.../modulo-1",
      "harness_components_present": ["Tools (1)", "Context-seed (3)"],
      "task_relative_path": "tasks/challenge.md",
      "time_budget_minutes": 25
    },
    ...
  ]
}
```

### Every run — one command in, one command out

```bash
# 1) Pre-flight + snapshot + render prompts + emit invocations.
python3 webinar-meta/skills/launch-isolated-module-agents/orchestrate.py <angle-root>
```

Output between the lines `BEGIN_INVOCATIONS` and `END_INVOCATIONS` is a JSON array. The parent assistant parses it and fires one Agent() call per entry, all in a *single message*, `run_in_background: true`. (A python script can't call Agent — only an assistant can.)

```bash
# 2) After all agents return (you'll be notified per agent), verify isolation.
python3 webinar-meta/skills/launch-isolated-module-agents/orchestrate.py <angle-root> --verify
```

The verify run prints per-module pass/fail across V1 self-report, V2 filesystem diff, V3 hook log. Any FAIL is workshop-relevant data — capture in the angle's run log.

### When a subagent can't write REPORT.md

Recurring friction (all 3 angles): the general-purpose subagent system prompt blocks `Write` on `.md` files matching `report|findings|summary|analysis.*\.md$`. The agent returns the report content in text. The parent assistant persists it to `<module>/REPORT.md` manually. The prompt template asks the agent to flag this so you spot it.

## What this skill deliberately does NOT do

- Does not enforce intra-angle isolation in the OS sense. Cross-KB / cross-angle is hard via #2 + #3. Intra-angle (M1 reading M2) stays soft + audited.
- Does not parse the agent's tool-call JSONL transcript. The transcript is too large to load into context and the harness explicitly warns against it. We use agent self-report + filesystem diff + hook log instead — all three are small and auditable.
- Does not handle `isolation: "worktree"`. Disk cost was prohibitive in our repo (3.2 GB data × N agents). Documented but not wired.

## Future work

- **Per-agent allowlists** via cwd-aware hook (write `_launch/<timestamp>/agent-<n>-allowlist.txt`, have the hook identify the calling subagent from its tool_use_id and look up its allowlist). Promotes intra-angle isolation from soft to hard.
- **Container-use variant** for the on-stage finale (NC-25). One Docker per agent, mount only the allowed paths.
- **Per-angle manifest generators** that infer module-paths and components-present from the angle's folder structure (currently the manifest is built by hand).
