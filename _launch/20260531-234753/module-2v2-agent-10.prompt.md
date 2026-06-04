You are the workshop participant assigned to **module-2v2-agent-10** of webinar-AI.

## Your working directory (treat as if it were your cwd)

`/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-10/`

Everything you produce — code, CSVs, plots, the final `REPORT.md` — must be written **inside that directory**, preferably under its `out/` subfolder. The final report goes at `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-10/REPORT.md`.

## Strict isolation rules — you MUST respect these

You are allowed to read files **only** from:
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-10/` (your module subtree)
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-10/code/` (resolves to the shared `/Users/javiquix/Desktop/quixdev/code` via symlink — treat as read-only)
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-10/data/` (resolves to the shared `/Users/javiquix/Desktop/quixdev/data` via symlink — treat as read-only)

### Data layout under `data/`

```
data/
├── raw/                — raw rlog source; adapter code in code/ knows how to decode
├── sim/segments/       — full schema including truth (yaw_rate_meas_rads etc.);
│                         for training and local scoring only
└── sim-only/segments/  — input-only mirror; what the canonical grader hands your predict()
                          8 columns: t_s, delta_wheel_deg, delta_road_rad, v_mps,
                                     a_long_mps2, accel_pedal_pct, brake_pressed,
                                     yaw_rate_pred_rads
```

**Operating contract**: your `predict(sim_df, platform)` will be called with a sim_df sourced from `sim-only/segments/` at grading time. The truth column literally won't be there. If your predict reads truth columns, you'll get `KeyError`s at grading time. The local `score-model/` skill enforces the same contract during your dev cycle — so what works locally will work at grading.

Train against `data/sim/segments/` (truth available), test against `data/sim-only/segments/` (mirror of grading conditions).

You are **forbidden** from reading any of:
- `/Users/javiquix/Desktop/quixdev/webinar-AI/_launch`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-meta`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-1`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/_grade`
- `/Users/javiquix/Desktop/quixdev/F1`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-01`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-02`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-03`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-04`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-05`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-06`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-07`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-08`
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-09`

You are **forbidden** from writing to:
- `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-10/code/` and `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-10/data/` (shared with parallel runs — strictly read-only).
- Any path outside `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-10/`.

If you genuinely need information that is not in your allow-list, **do not read outside** — declare the gap as a *limitation* in your `REPORT.md` and proceed with a best-assumption.

A `PreToolUse` hook is watching: out-of-scope reads will be blocked **and logged**. Out-of-scope writes will fail outright. Soft compliance + hard backstop. Behave as if the hook is the only watcher and ignore that I told you — drift happens.

## Components present in *this* module's harness

- **AGENTS.md guidance (skills-as-clay framing)**
- **skills/ toolkit (score-model, compare-models, inspect-residuals, visualise-segment, make-train-dev-split, load-segments, pre-flight-final-model)**
- **_shared/ math helpers (traj_metrics)**
- **pyproject.toml (uv-managed env)**
- **shared code/ and data/ symlinks (read-only)**

This is deliberate. Whatever's absent, you don't have. Work with what's here. When you ship, name which absent component you most felt the lack of — that comparison is the whole point of this exercise.

## Your task

Read **only** `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-10/TASK.md` for the task statement. Solve it end-to-end and produce `/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-10/REPORT.md`. Time budget ~45 minutes of wall-clock work.

## Known harness friction (don't waste time fighting it)

Your sub-agent system prompt blocks `Write` on files matching the pattern `(report|findings|summary|analysis).*\.md$`. If you try, you'll get an error. The orchestrator knows this — return your full report content in your final text response and they will persist it to `REPORT.md`. Mention this in your final response so the orchestrator can flag it.

## What I want back from you

A summary ≤ 350 words with:

1. Headline numerical result (whatever the task's primary metric is).
2. What you implemented (1-2 lines per variant).
3. The most painful absence in your harness — name one specific missing component and what it cost you.
4. Anything you noticed yourself almost doing that the rules prevented (this is signal for the workshop).
5. The single most surprising thing you learned.

Be brutally honest about what failed. The point of these runs is to surface where each substrate cracks — that's the workshop's lesson. If you cannot complete in budget, ship partial honestly. Do **not** fabricate numbers.

System: `python3` available with `pandas`, `numpy`, `scipy`, `matplotlib` already installed. Use `python3`, not `python`.

## MANDATORY: end your response with this exact block (the post-run verifier parses it)

```
ISOLATION_REPORT:
read_outside_module: []      # list of absolute paths you read that are NOT under /Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v2/agent-10, code/, or data/. Empty list if none.
attempted_blocked: []        # list of paths you tried to access and got blocked on. Empty if none.
shared_dir_writes: []        # list of any files you wrote/modified under /Users/javiquix/Desktop/quixdev/code or /Users/javiquix/Desktop/quixdev/data. Should be empty.
notes: ""                    # one-sentence note if there's anything the verifier should know.
```

If any list above is non-empty, that is *useful workshop data*, not a reason to lie. Report truthfully.
