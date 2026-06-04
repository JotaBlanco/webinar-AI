---
name: grade-cohort-reports
description: Canonical-evaluation grading for a cohort of agent submissions. Each agent's final-model is run programmatically (no LLM) against a fixed held-out validation pool; the cohort is summarised into a comparable scorecard. Outputs cohort.{json,md,html,pdf} with interactive scatter, per-family bars, per-platform faceted scatter, per-segment boxplots, calibration cards, and a substrate-quality section.
when-to-load: When 2+ agents have shipped a `final-model/{manifest.json, predict.py}` against the same idea, and you want apples-to-apples KPIs across the cohort. NOT for single-agent grading; NOT for code review.
inputs: An idea-id (filename stem under webinar-meta/domain-knowledge-challenges/) + one or more globs to each agent's final-model folder.
outputs: cohort.json + cohort.md (per agent + per family + per platform + per segment + reconstruction quality). HTML + PDF in iter 2.
load-cost: ~200 tokens metadata, ~700 tokens body.
---

# grade-cohort-reports — canonical-only edition

## Why this skill exists

We run N agents against the same idea (e.g. lateral-fidelity yaw-rate prediction). Each agent ships a `final-model/` folder. We need ONE comparable number per KPI per agent so we can rank, plot, and learn from the cohort.

**Agents' self-reported headlines are not comparable.** They each picked different train/test splits, different segment subsets, different metric definitions. The only honest comparison is to re-run every agent's predict function against the same held-out validation pool under identical conditions. That's what this skill does.

## Architecture

```
orchestrate.py grade --idea-id <id> --agent-folders <glob>
                              │
                              ▼
                       baseline.py          (cache hit if hash matches)
                              │              caches under baselines/<idea>.baseline.json
                              ▼
                       canonical_eval.py    (spawns N parallel subprocesses)
                              │              one per agent — worker.py
                              ▼
                       <out-dir>/canonical/<agent_id>.json
                              │
                              ▼
                       aggregate.py         → cohort.json   (every stat the renderers need)
                              │
                              ▼
                       report.py            → cohort.md
                                              (iter 2: + cohort.html + cohort.pdf + scatter SVG)
```

**No LLM is called in the default path.** The contract is: agents ship a `final-model/{manifest.json, predict.py, optional coeffs.json}`; `worker.py` imports `predict.py` in an isolated subprocess and runs it on each val segment.

## Files

| file | responsibility |
|---|---|
| `orchestrate.py`        | Single CLI entry. Default: `grade <idea> <folders>` runs the whole pipeline. |
| `baseline.py`           | Compute & cache V0 baseline. Hash-keyed on val pool + metric definition. |
| `baselines/<idea>.baseline.json` | Cached V0 RMSEs. Reused across runs; rebuilt if inputs change. |
| `canonical_eval.py`     | Discover agents, dispatch N workers in a thread pool, write per-agent JSONs. |
| `worker.py`             | Per-agent subprocess body. Imports agent's predict, streams val segments, accumulates yaw + CTE. |
| `traj_metrics.py`       | CTE integration + pooling helper (shared with baseline.py). |
| `aggregate.py`          | Reads per-agent JSONs → emits `cohort.json` with every stat the renderer needs. |
| `report.py`             | Renders `cohort.md`. |
| `chart.py`              | Plotly figures (headline scatter, family bars, per-platform faceted scatter, per-segment boxplot). Exports both interactive HTML divs and static SVG. |
| `report_html.py`        | Renders `cohort.html` (interactive plotly via CDN) and `cohort.print.html` (static SVG, no JS). Uses CSS from quix-report-styling light theme. |
| `report_pdf.py`         | Renders `cohort.pdf` from `cohort.print.html` via weasyprint. |
| `.venv/`                | Skill-local virtualenv with plotly + kaleido + weasyprint + pandas + numpy. The orchestrator auto-uses it for HTML/PDF renderers; canonical eval itself runs on system python. |

## Per-agent JSON schema (`canonical/<agent_id>.json`)

```json
{
  "agent_id": "m1-agent-01",
  "agent_folder": "...",
  "format_checks": {
    "agent_folder_exists": true,
    "has_manifest_json": true,
    "manifest_parsable": true,
    "manifest_declares_predict_callable": true,
    "manifest_declares_platform_support": true,
    "has_predict_py": true,
    "has_coeffs_json": true,
    "has_report": true
  },
  "manifest": { ... },
  "execution": {
    "status": "ok" | "failed",
    "reason": null | "missing_manifest_json" | "import_failed" | "no_segments_succeeded" | ...,
    "n_segments_attempted": 130,
    "n_segments_succeeded": 122,
    "n_segments_skipped_unsupported_platform": 8,
    "n_segments_runtime_error": 0,
    "first_runtime_error": null,
    "wall_time_seconds": 2.1
  },
  "yaw_rate":  { "baseline_rmse", "agent_rmse", "improvement_pct", "n_samples" },
  "cte":       { "baseline_rmse_meters", "agent_rmse_meters", "improvement_pct", ... },
  "per_platform": { "FORD_F_150_LIGHTNING_MK1": { yaw, cte, n_segments_ok, ... }, ... },
  "per_segment":  [ { segment, platform, yaw_rmse, cte_rmse_m }, ... ],
  "coefficients": { ... }
}
```

**Failed agents emit `yaw_rate: null` and `cte: null`** — no fake zeros, no fabricated numbers. The aggregator surfaces them as a separate cohort-failure section, not as zero performers.

## Required agent contract

Every agent must ship under their `final-model/` folder:

- `manifest.json` with `predict_callable: "predict.py:predict"` and `platform_support: ["FORD_..."]`
- `predict.py` defining `def predict(sim_df: pd.DataFrame, platform: str) -> pd.DataFrame` returning `yaw_rate_pred_rads`

Anything else is optional. `coeffs.json` is conventional; `REPORT.md` is informational only (not used by the canonical pass).

## Failure semantics

| Failure | Reason in JSON | What happens |
|---|---|---|
| Agent missed the deliverable | `missing_predict_py`, `missing_manifest_json` | No metrics emitted; reported in reconstruction-quality section |
| Manifest malformed | `manifest_json_invalid` | Same as above |
| predict.py raises on import | `import_failed` + traceback first line | Same; first_runtime_error captured |
| predict crashes per-segment | n_segments_runtime_error > 0 | Partial credit if other segments worked; first error captured |
| All segments failed | `no_segments_succeeded` | No metrics; failure surfaced |
| Worker subprocess timed out | `subprocess_timeout` | No metrics |

## Iteration roadmap

- **iter 1 (shipped):** canonical pipeline + cohort.md, all stats in cohort.json.
- **iter 2 (shipped):** cohort.html (interactive plotly) + cohort.pdf (weasyprint) via quix-report-styling light theme; scatter, family bars, per-platform faceted scatter, boxplots, calibration cards.
- **iter 3:** `--with-self-reported` diagnostic mode — extract each agent's claimed yaw/CTE Δ% from their REPORT.md, compare to canonical, surface the gap as a self-awareness signal.

## Outputs per run (under `_grade/<ts>/`)

```
cohort.json            machine-readable; everything the renderer needs
cohort.md              human-readable markdown
cohort.html            interactive — open in a browser; plotly hovers / zoom
cohort.print.html      print-friendly (static SVG, no JS); intermediate for PDF
cohort.pdf             PDF via weasyprint — same content as cohort.html
canonical/<agent>.json one per agent, full scorecard including per-segment data
canonical/baseline.json the V0 baseline used this run
canonical/agent-folders.json   the agent→folder/family map
canonical/run-summary.json     wall-time, n_ok, concurrency, baseline cache key
```

## What this skill does NOT do

- Does not call an LLM on the default path (canonical mode is pure Python).
- Does not score code quality, prose, or rubric hygiene. (Iter 3 adds a small self-reporting diagnostic, not a rubric pass.)
- Does not normalise units across agents — it controls for them by running everyone's model under one fixed setup.
- Does not modify any file under `eval_data_root` (read-only by contract) or agent folders.
