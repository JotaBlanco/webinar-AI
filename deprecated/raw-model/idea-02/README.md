# raw-model / idea-02 — naked-prompt baseline

Ten isolated agents are launched in parallel here, each receiving **only** the naked Idea-02 prompt
(from [webinar-00/domain-knowledge-challenges/idea-02-longitudinal-closed-loop.md](../../webinar-00/domain-knowledge-challenges/idea-02-longitudinal-closed-loop.md), block "The naked prompt") plus access to `./code/` and `./data/` symlinks.

The 10 runs give statistical signal on what a raw model produces with zero substrate. Each `agent-NN/`
is independent — no AGENTS.md, no skill, no task file, no harness components. The folder layout is the
only thing the agent gets for free.

## Structure

```
idea-02/
├── README.md                    # this file
├── prompt.md                    # the exact prompt sent to every agent (for the record)
├── _launch/<timestamp>/
│   ├── snapshot.txt             # md5 of code/ and data/ before launch — proves agents didn't mutate them
│   └── invocations.json         # the exact Agent() calls fired
├── _launch/LATEST               # text file naming the most recent run timestamp
└── agent-{01..10}/
    ├── code -> ../../../code    # symlink to shared codebase (read-only by contract)
    ├── data -> ../../../data    # symlink to shared data (read-only by contract)
    ├── tools/                   # scratch space for any scripts the agent writes
    ├── out/                     # scratch space for any artefacts the agent produces
    └── REPORT.md                # the agent's final report (persisted by the parent assistant from the
                                 # agent's text response — subagent harness blocks Write on report.md)
```

## Isolation

- **Hard (repo-wide hook)**: `.claude/settings.json` runs `hook-blocker.py` on every Read/Bash/Edit/Write.
  It blocks reads of `webinar-00/domain-knowledge-challenges/**` (which contains the canonical answer for
  every idea, including this one), `webinar-angle-*/{_shared,_launch,_observations}/**`, RUN-LOG.md,
  process-log.md, plus the F1 KBs. Every blocked attempt is appended to `<repo-root>/.claude/blocked-attempts.log`.
- **Soft (prompt)**: agents are told not to read sibling `agent-NN/` folders, raw-model/idea-01 (a prior
  baseline that could prime them), or any `webinar-angle-*/modulo-*/` folder. Ten parallel background
  subagents start before any of them produces output, so the race naturally limits sibling leakage.

## Why this idea is harder than idea-01

Idea-01 asked the agent to attribute improvements within a fixed contract (which channel was clamped vs
predicted stayed the same). Idea-02 asks the agent to **change the contract**: remove measured longitudinal
speed as an input and build a model that predicts it from scratch. The dominant failure mode (per the trap
analysis in the canonical idea file) is **soft re-clamping** — removing the named input and silently
re-introducing it via a downstream sensor (wheel speed, ABS, sensed torque) that the model is effectively
being told its own answer through.

The 10 raw runs measure how often a model with zero substrate falls into this and the five other traps
in the idea-02 catalogue.

## Comparing to angle baselines

Each agent receives the **same naked prompt** as `webinar-00/domain-knowledge-challenges/idea-02-longitudinal-closed-loop.md`.
The angle modules will wrap this in task-files with progressively more substrate (M1 → M4). The 10 raw runs
here are the **M0 baseline** against which the substrate gains should be measured.
