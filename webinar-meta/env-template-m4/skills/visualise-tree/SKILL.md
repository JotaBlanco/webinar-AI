---
name: visualise-tree
description: Render `TREE.json` as an ASCII or markdown tree showing the search frontier — every node with its parent linkage, rung tag, dev-CV score, gate status, and routing decision. Optionally emit a PNG using matplotlib. Use to read the search at a glance, spot stagnant branches, and confirm structural diversity before declaring done. The tree visualisation is what makes the tree-search legible — without it the search is invisible to both the agent and the cohort reviewer.
when-to-invoke: Mid-run, after every ~5 `iterate` calls, to see whether the search is exploring or collapsing on one branch. Always run before the final preflight — preflight uses your reading of the tree to confirm structural diversity. Useful at session start in a fresh-context restart to see what the previous branch ruled out.
when-NOT-to-invoke: As a substitute for reading `MODELS.md`. The tree shows search shape; `MODELS.md` shows individual candidate verdicts. Use both.
inputs: tree_path (str or Path, default `TREE.json` at template root), format (`ascii | markdown | png`, default `ascii`), highlight (str — node id or name to highlight, default current leader).
outputs: str (the rendered tree) or Path (if `format=png`).
load-cost: ~140 tokens metadata, ~220 tokens body.
---

# visualise-tree

## What it shows

A tree of every candidate model the search has visited, with parent linkage. Each node displays:

- **Rung tag** (`R0 | R1 | R2 | R3 | ORTH`) — the structural level.
- **Dev-CV pooled yaw RMSE** (mean only; `±σ` in markdown mode).
- **Δ% vs V1** signed (the headline number).
- **Gate status** as a glyph: `✓` pass, `△` warn (with reason count), `✗` fail.
- **Verdict**: `kept | shelved | shipped | leader` (current leader is highlighted).

ASCII rendering (default):

```
v1  (R0, 0.005874 / 56.81)
├─ bias-corrected   R0   0.005843 (-0.5%)  ✓ leader
│   ├─ bias+steer-d R0   0.005827 (-0.8%)  △(1)  kept
│   └─ bias+v-lag   R0   0.005871 (-0.0%)  △(1)  shelved
├─ ridge-residual   ORTH 0.005810 (-1.1%)  ✓ kept
│   └─ gb-residual  ORTH 0.005634 (-4.1%)  ✓ leader ★
└─ dyn-st-carParams R1   0.006520 (+11.0%) ✗ shelved (under-param)
```

The `★` marks whatever the agent's `--highlight` argument names (default = current leader). The tree is rendered depth-first, eldest-first, so the most-developed branch is leftmost.

## Spotting stagnation

A branch with ≥3 consecutive `△` or `✗` is the visual signal for stagnation. The `iterate` skill flags this in `result["stagnation"]`; the tree shows you the shape that produced the flag.

## Spotting collapse

If every R-tag in the tree is `R0` and there are no `ORTH` or `R1`/`R2` nodes, the cohort failure mode of m3.v2 (every agent piles up at the rung-0 local optimum) has recurred. The pre-flight check warns; this skill is how you see it before preflight does.

## Markdown mode

`format="markdown"` returns the same tree as a markdown nested list, with each node hyperlinked to its `models/<name>/assessment.md`. Useful when shipping the tree in `REPORT.md`.

## PNG mode

`format="png"` writes a PNG of the tree to `_artifacts/tree-<timestamp>.png` using matplotlib. Useful for webinar demos and for the closing artifact. Requires matplotlib in the env.

## Usage

```python
from skills.visualise_tree.viz import visualise_tree
print(visualise_tree(format="ascii"))
visualise_tree(format="png", highlight="gb-residual")
```

## Extending this skill

Add columns by extending `_render_node` in `viz.py`. Common requests: per-platform Δ% breakdown, gate reason expansion, age of node. Keep the default ASCII rendering tight — one line per node — so the tree fits on a terminal.
