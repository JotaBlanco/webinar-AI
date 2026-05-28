# raw-model / idea-01 — naked-prompt baseline

Five isolated agents are launched in parallel here, each receiving **only** the naked Idea-01 prompt
(from [webinar-00/domain-knowledge-challenges/idea-01-lateral-attribution.md](../../webinar-00/domain-knowledge-challenges/idea-01-lateral-attribution.md), block "The naked prompt") plus access to `./code/` and `./data/` symlinks.

The 5 runs give statistical signal on what a raw model produces with zero substrate. Each `agent-NN/`
is independent — no AGENTS.md, no skill, no task file, no harness components. The folder layout is the
only thing the agent gets for free.

## Structure

```
idea-01/
├── README.md                    # this file
├── prompt.md                    # the exact prompt sent to every agent (for the record)
├── _launch/<timestamp>/
│   ├── snapshot.txt             # md5 of code/ and data/ before launch — proves agents didn't mutate them
│   └── invocations.json         # the exact Agent() calls fired
└── agent-{01..05}/
    ├── code -> ../../../code    # symlink to shared codebase (read-only by contract)
    ├── data -> ../../../data    # symlink to shared data (read-only by contract)
    ├── tools/                   # scratch space for any scripts the agent writes
    ├── out/                     # scratch space for any artefacts the agent produces
    └── REPORT.md                # the agent's final report (persisted by the parent assistant from the
                                 # agent's text response — subagent harness blocks Write on report.md)
```

## Isolation

- **Hard (repo-wide hook)**: `.claude/settings.json` runs `hook-blocker.py` on every Read/Bash/Edit/Write.
  It blocks reads of `webinar-00/domain-knowledge-challenges/**` (which contains the canonical answer),
  `webinar-angle-*/{_shared,_launch,_observations}/**`, RUN-LOG.md, process-log.md, plus the F1 KBs.
  Every blocked attempt is appended to `<repo-root>/.claude/blocked-attempts.log`.
- **Soft (prompt)**: agents are told not to read sibling `agent-NN/` folders or any `webinar-angle-*/modulo-*/`
  (which contain prior reports that could contaminate the baseline). Five parallel background subagents start
  before any of them produces output, so the race naturally limits sibling leakage.

## Comparing to the angle-A/B/C baselines

Each agent receives the **same naked prompt** as `webinar-00/domain-knowledge-challenges/idea-01-lateral-attribution.md`.
This is identical to what `webinar-angle-A/modulo-1/` etc. are SUPPOSED to receive (the angle modules wrap it
in a task-file with extra hints, intentionally). The 5 raw runs are the M0 baseline against which the M1..M4
substrate gains in each angle should be measured.
