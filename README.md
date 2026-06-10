# webinar-AI

Materials for the Quix webinar **"The F1 Playbook for AI-Assisted Engineering"** — the slide deck, the cohort-experiment harness, and the runnable code and data the agents work against.

📊 **[View the presentation →](https://quixio.github.io/webinar-AI/)**

The repo is organised around three audiences. Pick the one that matches what you came here to do.

---

## 1. I just want to see the slides

The deck is a set of standalone HTML files under [webinar-presentation/](webinar-presentation/). There is no central runner — each slide is its own page — but [webinar-presentation/presentation-index.html](webinar-presentation/presentation-index.html) links to every slide in order. Open it and click through.

```bash
open webinar-presentation/presentation-index.html
```

Slide order, in case you want to jump:

| # | Folder | Purpose |
|---|---|---|
| 1 | [00-first/](webinar-presentation/00-first/) | Title slide (full-bleed background video) |
| 2 | [01-intro/](webinar-presentation/01-intro/) | "Coding ≠ engineering" framing |
| 3 | [eng-problem/](webinar-presentation/eng-problem/) | The engineering problem we're attacking |
| 4 | [02-ladder/](webinar-presentation/02-ladder/) | The four-level capability ladder |
| 5–8 | [level-01/](webinar-presentation/level-01/) … [level-04/](webinar-presentation/level-04/) | One slide per rung of the ladder |
| 9 | [modules-results/](webinar-presentation/modules-results/) | Per-level results and the progressive overlay |
| 10 | [thank-you/](webinar-presentation/thank-you/) | Closing slide |

Anything under [webinar-presentation/templates/](webinar-presentation/templates/) or folders prefixed `option-` / `variant-` are design explorations, not part of the live deck. The chosen baseline visual language is Cosmic ([templates/01-cosmic.html](webinar-presentation/templates/01-cosmic.html)).

---

## 2. I want to understand the experiment

The webinar's claim is that **substrate** — what the agent has around it (tools, skills, data, constraints) — is more leverage than the prompt. To test that, we run the same engineering challenge against four progressively richer harnesses (the "ladder"), one per **module**.

### The challenges

Two engineering challenges, both grounded in vehicle dynamics on real openpilot CAN logs. Each prompt is **naked** — it names the goal and the deliverable contract and nothing else. The rubric lives outside the prompt.

- **Challenge 1 — Lateral fidelity.** Improve the yaw-rate / cross-track prediction of a baseline kinematic single-track (KS) model. Graded on yaw-rate RMSE and distance-resampled cross-track-error RMSE.
- **Challenge 2 — Longitudinal closed-loop.** Predict the longitudinal speed channel itself (the current model takes it as input). Graded on speed RMSE and per-segment distance-error RMSE.

Full prompts: [webinar-meta/engineering-challenges/README.md](webinar-meta/engineering-challenges/README.md).

### The four modules (rungs of the ladder)

Each module is a per-agent working directory. Inside each `agent-XX/` there is a `TASK.md`, a `REPORT.md` the agent writes, and `code/` + `data/` symlinks into the shared spine.

| Module | What the agent gets on top of `TASK.md`, `code/`, `data/` |
|---|---|
| [module-1/](module-1/) | Bare cwd — just the task and the data |
| [module-2/](module-2/) | Adds an `AGENTS.md` and skills (`_shared/traj_metrics.py`, etc.) |
| [module-3/](module-3/) | Richer harness on top of module 2 |
| [module-4/](module-4/) | Full substrate — closest to what a senior engineer would have |

Each module has ten agents (`agent-01` … `agent-10`) so the cohort comparison is statistical, not anecdotal.

### The code and data the agents share

- [code/](code/) — the runnable spine. KS model, parameter sets, rlog reader, baseline `v1_baseline.py`, viz helpers. See [code/_README.md](code/_README.md) for the file-by-file map.
- [data/](data/) — `raw/` (rlog.zst), `sim/` (decoded + KS-baseline + truth), `sim-only/` (truth-stripped, agent-facing). **Gitignored**; per-agent `data/` symlinks point into the top-level tree.

---

## 3. I want to extend it (data, agents, grading)

All extension paths live under [webinar-meta/](webinar-meta/) and are wired as **skills** the orchestrator (or a parent assistant) invokes. The skills are self-documenting — each has a `SKILL.md` at its root with the full contract.

### Add a new car platform (download → build sim data)

Two skills, run in sequence:

```bash
# 1. Discover what's available on comma.ai's commaCarSegments dataset, then download.
#    No-arg run = discovery view (what's suitable for which challenge, how much we already have).
python3 -m webinar-meta.skills.download-rlog-data
#    Then with a pick:
python3 -m webinar-meta.skills.download-rlog-data --platform HYUNDAI_IONIQ_5 --train 50 --val 10

# 2. Decode rlogs → sim.csv (with KS baseline + truth) and the truth-stripped sim-only/ mirror.
python3 webinar-meta/skills/build-simdata/build_simdata.py HYUNDAI_IONIQ_5
```

- [webinar-meta/skills/download-rlog-data/](webinar-meta/skills/download-rlog-data/) — discovery, suitability check, seeded train/val split, fetch.
- [webinar-meta/skills/build-simdata/](webinar-meta/skills/build-simdata/) — per-OEM adapters (DBCs live here), KS-baseline computation, sim/sim-only emit.

Data roots are read from [webinar-meta/data-paths.json](webinar-meta/data-paths.json) — both skills pick changes up from there.

### Add a new agent to a module

Each `module-N/agent-XX/` is provisioned from a template under [webinar-meta/env-template-m1/](webinar-meta/env-template-m1/) … `env-template-m4/`. To add another agent slot, copy the matching template into a new `agent-NN/` folder and add it to the module's launch config under [webinar-meta/launch-configs/](webinar-meta/launch-configs/).

### Launch a cohort (N isolated agents in parallel)

The [launch-isolated-module-agents](webinar-meta/skills/launch-isolated-module-agents/) skill enforces four layers of isolation (prompt + settings deny rules + pre-tool hook + post-run audit) so each agent sees only its own subtree plus shared `code/` and `data/`. One script drives a run:

```bash
# Pre-flight + materialise prompts + emit Agent() invocations.
python3 webinar-meta/skills/launch-isolated-module-agents/orchestrate.py <module-launch-config>

# After the parent assistant fires the N Agent() calls and they finish:
python3 webinar-meta/skills/launch-isolated-module-agents/orchestrate.py <module-launch-config> --verify
```

Launch artifacts (prompts, pre-flight reports, blocked-attempt logs) land under [cohort-runs/_launch/](cohort-runs/_launch/), timestamped per run. The active config consumed by the orchestrator is [cohort-runs/.launch-config.json](cohort-runs/.launch-config.json).

### Grade a cohort

[grade-cohort-reports](webinar-meta/skills/grade-cohort-reports/) re-runs every agent's `final-model/predict.py` against the same held-out validation pool — agents' self-reported headlines are not comparable (different splits, different metrics) so the grader recomputes from scratch.

```bash
python3 webinar-meta/skills/grade-cohort-reports/orchestrate.py \
    --idea idea-01-lateral-attribution \
    --agents 'module-*/agent-*/final-model'
```

Outputs `cohort.{json,md,html,pdf}` with per-agent / per-family / per-platform / per-segment breakdowns under [cohort-runs/_grade/](cohort-runs/_grade/). Canonical judge prompts live at the root of that dir.

### Visualise an agent's prediction vs truth

[webinar-meta/visualisation/](webinar-meta/visualisation/) — `compare.py`, `compare_plotly.py`, `compare_rerun.py` overlay an agent's `predict()` output against the truth channels in `sim.csv`.

---

## Repo map

```
webinar-AI/
├── webinar-presentation/        # the deck (audience 1)
├── webinar-meta/                # experiment harness (audience 3)
│   ├── engineering-challenges/  # the naked prompts + rubrics
│   ├── env-template-m{1..4}/    # per-module agent environment templates
│   ├── launch-configs/          # per-module launch configs
│   ├── skills/
│   │   ├── download-rlog-data/
│   │   ├── build-simdata/
│   │   ├── launch-isolated-module-agents/
│   │   └── grade-cohort-reports/
│   ├── visualisation/           # truth-vs-prediction overlays
│   └── data-paths.json          # single source of truth for data roots
├── module-1/ … module-4/        # per-module cohorts (10 agents each) (audience 2)
├── code/                        # shared runnable spine — KS model, rlog reader, baselines
├── data/                        # raw / sim / sim-only (gitignored, symlinked into agents)
└── cohort-runs/                 # timestamped launch + grade artifacts
    ├── _launch/
    ├── _grade/
    └── .launch-config.json
```
