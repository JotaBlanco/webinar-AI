---
name: grade-cohort-reports
description: Grade a cohort of agent reports against the rubric in a `webinar-00/domain-knowledge-challenges/idea-NN-*.md` file. Designed for the case where multiple agents (across raw-model baselines, multiple angles, or multiple modules) solved the same idea and we want a consistent, evidence-quoting comparison of how well each did. Emits a per-agent scorecard JSON + a cohort summary markdown.
when-to-load: When you want to grade 2+ reports against a canonical rubric. NOT for single-agent grading (use the rubric file directly), NOT for code review.
inputs: An idea-id (filename stem under `webinar-00/domain-knowledge-challenges/`) and one or more report paths or globs.
outputs: One JSON scorecard per agent + a cohort.md + a cohort.json under `_grade/<timestamp>/`.
load-cost: ~280 tokens metadata, ~1100 tokens body.
---

# grade-cohort-reports

## Why this skill exists

We have N runs of the same idea — sometimes a 5-agent raw-model baseline (`raw-model/idea-01/agent-*/REPORT.md`), sometimes the four module reports of a single angle, sometimes a cross-angle comparison. We want to answer:

1. **How did each agent score against the canonical rubric?** (per-item, with evidence)
2. **Where did the cohort converge or diverge?** (platform pick, primary metric, top contributor)
3. **Which rubric items have a high trap-trip rate?** (the rubric items the cohort consistently misses — these point at the substrate gap that matters)
4. **What's the spread of headline numbers across the cohort?** (range, not a winner — different agents pick different metrics; the spread *is* the signal)

The rubric is **not** something we write — it already exists in [webinar-00/domain-knowledge-challenges/](../../domain-knowledge-challenges/), authored by the domain expert when the idea was framed. The skill reuses that rubric block verbatim.

## Architecture — judge-as-subagent

Mirrors the [launch-isolated-module-agents](../launch-isolated-module-agents/SKILL.md) pattern:

1. **`prepare.py`** — discovers reports (from explicit paths or globs), loads the rubric from the challenge file, materialises one judge prompt per report under `_grade/<timestamp>/judge-<agent_id>.prompt.md`, writes `invocations.json` with one Agent() call per report.
2. **Parent assistant fires the N grading subagents** in a single message, `run_in_background: true`. Each judge returns a strict-JSON scorecard.
3. **`aggregate.py`** — reads each subagent's JSON output, writes per-agent `<agent_id>.json` + `<agent_id>.md`, and a cohort `cohort.md` + `cohort.json` with pass-rate-per-item, convergence counts, and the headline spread table.
4. **`orchestrate.py`** — one-call entry point. `orchestrate.py grade <idea-id> [report paths/globs...]` prepares + emits invocations. `orchestrate.py aggregate [--grade-dir DIR]` does the post-grading rollup.

## Design decisions — read these before changing the skill

### Judge granularity: one call per report, not per (report × rubric item)

The rubric items in `idea-NN-*.md` are largely orthogonal, and a single judge call sees the whole report once — much cheaper than `N × items` calls. The judge returns a list of scorecards, one per rubric item, each with its own evidence quote. If items start contaminating each other (e.g., the judge halos a borderline pass because the report was strong overall), split into per-item calls then.

### Generous-on-paraphrase + quote-required

The judge credits paraphrases (an agent saying "I scored against `yaw_rate_meas_rads`, the measured channel from Ford CAN" satisfies a rubric item asking for "scores against a measured channel"). But **every credited item must include a verbatim quote** from the report — the quote IS the audit trail. No quote → automatic FAIL. This is the cheapest defence against the judge softly drifting toward "looks good to me."

### No oracle for headline numbers

Agents pick different metrics (yaw-rate RMSE in rad/s vs mrad/s vs deg/s; pooled vs train/test; Ford-only vs Tesla-fabricated). There is no single "correct" headline. The aggregator emits a table of `(agent_id, primary_metric, baseline, final, improvement)` as the agent stated them — no normalisation, no ranking. The **variance** across the cohort is the signal.

### Canonical eval = held-out val-data (since 2026-05-28)

The canonical-eval pipeline (`prepare_canonical.py` + per-agent judges) scores every agent's reconstructed model against a route-stratified validation hold-out that no agent has seen. The val-data root is declared in the idea's `.canonical.yaml` as `eval_data_root:` (absolute path, outside the repo). Segment globs in the YAML are resolved against that root.

Implication for cohort interpretation: agents whose "headline" comes from per-segment overfitting (e.g. fitting a bias on each segment they were given) will score canonically lower than they self-reported, because the val segments are unseen. Agents whose model is a parameterised function generalising across segments will score similarly to their self-report. The gap between self-reported and canonical &Delta;% is now a generalisation diagnostic, not a "different evaluation surface" artefact.

### Honesty flags are tracked separately

"Did the agent declare a limitation" is more important than "is their number good." A 7.8 % improvement with an honest "I had no truth channel and synthesised one from wheel-speed differentials" is qualitatively different from a 34 % improvement that silently glosses over a data-cleaning trick. The aggregator surfaces `declared_limitations: count` and `named_data_gap: bool` as first-class fields.

### Cross-angle cohorts

A cohort can span the raw-model baseline AND any number of angle modules that targeted the same idea. The skill takes report paths or globs — it doesn't assume folder layout. For metadata (e.g., which substrate components were present in each agent's harness), pass an optional `--manifest <file.json>` mapping report paths to substrate descriptors; the aggregator surfaces these as columns next to the scores.

## Schema — the judge's strict-JSON output

```json
{
  "agent_id": "<short id parsed from report path>",
  "report_path": "<absolute path>",
  "items": [
    {
      "id": "<rubric item id, e.g. truth-channel-correct>",
      "type": "binary|numeric",
      "result": true | false | null,
      "value": <number or null>,
      "threshold_met": true | false | null,
      "evidence": ["<verbatim quote from report>", ...],
      "reasoning": "<one sentence>"
    }
  ],
  "headline": {
    "primary_metric": "<verbatim>",
    "platform": "<verbatim>",
    "baseline_value": "<verbatim>",
    "final_value": "<verbatim>",
    "improvement": "<verbatim>",
    "top_contributor": "<verbatim or null>"
  },
  "honesty_flags": {
    "declared_limitations": <int>,
    "named_data_gap_or_missing_truth_channel": true | false,
    "fabricated_truth_or_proxy_undeclared": true | false
  }
}
```

## What this skill does NOT do

- Does not invent rubric items. If the challenge file's `success-metrics` block is thin, the cohort report will be thin — that's a signal to enrich the rubric, not to extend the skill.
- Does not score code quality, prose, or "did the agent follow the prompt structure." Off-topic for what the workshop measures.
- Does not normalise headline numbers across agents (see "No oracle" above).
- Does not call the Claude API directly — it relies on the parent assistant firing Agent() subagents as judges, consistent with the rest of this repo.
