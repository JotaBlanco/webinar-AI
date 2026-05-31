# Sample task — smoke test

> Compute the basic statistics of the numbers in `data/example.csv`. Are any values worth flagging as outliers?

## Why this task

Smoke test for the substrate. The `hello-world` skill in `skills/hello-world/SKILL.md` provides the procedure; the `compute_stats` helper in `tools/example_tool.py` does the work; the eval in `evals/hello_world_eval.py` verifies the answer.

If the agent answers this correctly *and* the eval passes, every layer of the substrate is wired:

- ✓ AGENTS.md loaded (the agent knows the project conventions).
- ✓ skills/ discovered (hello-world's metadata was inspected).
- ✓ skills/ body loaded on demand (the procedure was followed).
- ✓ tools/ reachable (compute_stats returned numbers).
- ✓ evals/ runnable (the eval ran and reported pass/fail).
- ✓ data/ readable (example.csv was loaded).

Delete this task once your first real domain task is in place.
