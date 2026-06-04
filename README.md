# webinar-AI

Materials for the Quix webinar **"The F1 Playbook for AI-Assisted Engineering"** — slides, cohort runs, grading, and the runnable code spine.

## Slides

The deck is a set of standalone HTML files under [webinar-presentation/](webinar-presentation/). There is **no central navigation** — each slide is its own page and you advance manually by opening the next folder's `index.html`.

### Open slide 1

```bash
open webinar-presentation/00-first/index.html
```

That's the title slide ([webinar-presentation/00-first/index.html](webinar-presentation/00-first/index.html)) — it has a full-bleed background video, so it must be served from the filesystem the browser can read; opening directly with `open` works on macOS.

### Slide order

| # | Folder | Purpose |
|---|---|---|
| 1 | [00-first/](webinar-presentation/00-first/) | Title slide |
| 2 | [01-intro/](webinar-presentation/01-intro/) | Intro — "coding ≠ engineering" framing |
| 3 | [eng-problem/](webinar-presentation/eng-problem/) | The engineering problem we're attacking |
| 4 | [02-ladder/](webinar-presentation/02-ladder/) | The four-level capability ladder |
| 5 | [level-01/](webinar-presentation/level-01/) | Level 1 — single agent, single task |
| 6 | [level-02/](webinar-presentation/level-02/) | Level 2 |
| 7 | [level-03/](webinar-presentation/level-03/) | Level 3 |
| 8 | [level-04/](webinar-presentation/level-04/) | Level 4 |
| 9 | [modules-results/](webinar-presentation/modules-results/) | Results per level (level-1.html … level-4.html, plus progressive.html) |
| 10 | [thank-you/](webinar-presentation/thank-you/) | Closing slide |

Folders prefixed with `option-`, `variant-`, or numbered design alternatives (e.g. [02-ladder/01-isometric.html](webinar-presentation/02-ladder/01-isometric.html)) are **design explorations**, not part of the live deck. The chosen baseline visual language is Cosmic ([templates/01-cosmic.html](webinar-presentation/templates/01-cosmic.html)).

### Making the slides easier to drive

Right now advancing means opening N tabs by hand. A few options, cheapest first:

1. **Serve the directory and bookmark each URL.** Run `python3 -m http.server 8000` from [webinar-presentation/](webinar-presentation/) and visit `http://localhost:8000/00-first/`, `http://localhost:8000/01-intro/`, etc. Cleaner than `file://` (background videos and any fetches behave normally) and you can `→` through bookmarks.
2. **Add prev/next links to each `index.html`.** A one-line `<a href="../01-intro/">Next →</a>` overlay per slide would turn the deck into a clickable sequence with no build step. Easiest persistent improvement.
3. **Wrap in an iframe-based runner.** A tiny `runner.html` with a hardcoded ordered list of slide folders + arrow-key navigation gets you a real keyboard-driven deck without touching the existing slides. ~30 lines.

Option 2 is probably the right next step if this deck gets reused.

## What's where

### Presentation
- [webinar-presentation/](webinar-presentation/) — slides (see above)
- [webinar-presentation/templates/](webinar-presentation/templates/) — six visual-style templates explored before settling on Cosmic

### Live demo / cohort runs
- [webinar-meta/](webinar-meta/) — the orchestration around the live agent runs
  - [orchestrator/](webinar-meta/orchestrator/) — drives the agent fleet
  - [skills/](webinar-meta/skills/) — skills the agents have access to
  - [launch-configs/](webinar-meta/launch-configs/) — per-level launch configuration
  - [env-template-LV01/](webinar-meta/env-template-LV01/) … `LV04/` — per-level agent environment templates
  - [domain-knowledge-challenges/](webinar-meta/domain-knowledge-challenges/) — the tasks the agents are graded on
  - [visualisation/](webinar-meta/visualisation/) — visualising agent outputs
- [_launch/](_launch/) — timestamped launch artifacts from each cohort run
- [_grade/](_grade/) — timestamped grading runs; canonical judge prompts at the root of this dir

### Module outputs (one folder per level / agent)
- [module-1/](module-1/) — Level 1 outputs, ten agents (`agent-01` … `agent-10`), each with `TASK.md`, `REPORT.md`, `code/`, `data/`, `final-model/`, `out/`
- [module-2/](module-2/), [module-3/](module-3/), [module-4/](module-4/) — same shape for levels 2–4

### Reference code
- [code/](code/) — the runnable CommonRoad spine: KS vehicle model, rlog adapters (Tesla, Ford), simdata generators. See [code/_README.md](code/_README.md) for the full file map.

### Data
- [data/](data/) — `raw/`, `sim/`, `sim-only/`. **Gitignored**; the working tree relies on symlinks into top-level `data/`, so cloning fresh requires repopulating it.

## Quick reference

```bash
# Open the deck
open webinar-presentation/00-first/index.html

# Or serve it for a cleaner experience
cd webinar-presentation && python3 -m http.server 8000

# Run the synthetic vehicle-model demo
cd code && python3 -m venv .venv && source .venv/bin/activate
pip install pycapnp zstandard cantools numpy scipy matplotlib pandas
python run_ks_synthetic.py
```
