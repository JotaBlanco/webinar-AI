---
name: hello-world
description: Smoke-test skill. Given a list of numbers in a CSV file, return basic statistics (mean, median, stdev) and flag any value more than 2 stdev from the mean as a candidate outlier. Use this to verify the harness loads skills correctly before adapting the template — delete once your first real skill is authored.
when-to-invoke: User asks to compute basic statistics over a numeric list, OR you are verifying the substrate is wired correctly. Not for any real domain question.
load-cost: ~50 tokens metadata, ~150 tokens body.
---

# hello-world

## Procedure

1. Read the CSV file path from the user's question (or default to `data/example.csv`).
2. Call the `compute_stats` helper in [`tools/example_tool.py`](../../tools/example_tool.py) — pass the file path, get back a dict with `mean`, `median`, `stdev`, and `outliers` (list of values >3σ from the mean).
3. Run the eval at [`evals/hello_world_eval.py`](../../evals/hello_world_eval.py) on the result. If it fails, report the failure mode — do **not** silently re-try.
4. Return a markdown summary — one line per statistic, one line listing outliers (or "no outliers detected"), one line stating eval pass/fail.

## Output shape

```
Statistics for <file>:
- mean: <value>
- median: <value>
- stdev: <value>
- outliers (>2σ): <list or "none">

Eval: <pass | fail — failure mode>
```

## Why this skill exists

It is the smoke test. If you can ask the agent the question in [`tasks/hello.md`](../../tasks/hello.md) and it returns the right answer with eval pass, your substrate is wired correctly — AGENTS.md is loading, skills are being discovered, tools are reachable, evals are runnable. Delete this skill (and its task, data fixture, and eval) once your first real domain skill is authored.
