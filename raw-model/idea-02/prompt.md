# Raw baseline prompt — idea-02

The exact prompt sent to each of the 10 parallel agents. Placeholder `{{NN}}` is filled with `01..10`.

---

You are agent **{{NN}}** of a 10-run statistical-baseline experiment. The other nine agents are running the same task simultaneously in sibling folders. You will never see their work; they will never see yours.

## Working directory

`/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-{{NN}}/`

Treat that path as if it were your cwd. All artefacts you produce — scripts, intermediate CSVs, plots, anything — go inside it (use `tools/` for scripts, `out/` for outputs).

## What you have access to

- `./code/` — symlink to a shared Python codebase. **Read-only by contract.** Browse it freely to find the model.
- `./data/` — symlink to a shared dataset. **Read-only by contract.**
- `python3` is on PATH with `pandas`, `numpy`, `scipy`, `matplotlib` already installed. Use `python3`, never `python`.

## What you are forbidden to read

- Any sibling agent folder: `../agent-01/`, `../agent-02/`, ..., `../agent-10/` except your own. Sibling reports would contaminate the baseline.
- Any other `raw-model/idea-*/` folder — those are prior baselines on related tasks and could prime your answer.
- Any `webinar-angle-*/modulo-*/` folder anywhere in the repo. Those contain prior solutions to related tasks — reading them defeats the experiment.
- Anything under `webinar-00/` (challenge metadata that includes the canonical answer to your task).
- Anything outside the `webinar-AI/` repo root, with the exception of standard system files / Python stdlib.

A repo-wide `PreToolUse` hook hard-blocks the most sensitive paths (challenge metadata, observations, run logs, sister KBs) and logs every blocked attempt. Cross-angle module reads and sibling-folder reads are **prompt-soft** — you are on your honour. Behave as if the hook caught everything; drift happens.

If you genuinely need information you can't access, **declare it as a limitation** in your final report and proceed with a best-effort assumption.

## Your task (this is everything — there is no other context)

> Our vehicle model currently takes measured longitudinal speed as an input — that's the crutch we need to remove. Build a longitudinal model that predicts that channel itself, accurately enough to stand on its own.

That is the whole brief. Nothing else has been given. The naked-ness is deliberate — ten agents receiving the same naked brief lets us measure what a model with zero substrate actually produces.

## Time budget

**~15 minutes** of wall-clock work. Ship partial honestly if you run out — do **not** fabricate numbers, do **not** stall on perfection.

## What to return

In your final response (a single text block), produce:

1. **Headline number** — your chosen primary metric, baseline value, final value.
2. **What you implemented** — 1-2 lines per change you made.
3. **How you validated** — name the mode (open-loop one-step vs closed-loop integration), the horizon, and the inputs you fed the new model. Be explicit about which inputs are commanded vs sensed.
4. **Regime breakdown** — error broken out by regime if you produced one (cruise / accel / brake / coast / cornering / combined-load). Aggregate-only is acceptable but flag it.
5. **Surprises** — anything you didn't expect to find in the code or data.
6. **Limitations** — what you couldn't access, what you couldn't figure out, what you'd want next.

### Known harness friction

Your subagent system prompt blocks `Write` on files matching `(report|findings|summary|analysis).*\.md$` (case sensitivity unknown). If that bites you, **do not fight it** — your full report content in the final response is what we want. The parent will persist it to `REPORT.md` afterwards. Mention any blocked write in your response so we can flag it.

You may freely write Python scripts under `tools/`, intermediate data under `out/`, and any non-report `.md` notes inside your folder.

## End your response with this exact block — verbatim, no markdown wrapping

```
ISOLATION_REPORT:
read_outside_allowed: []     # absolute paths you read that are NOT under your agent folder, ./code/, or ./data/
attempted_blocked: []        # paths the hook (or your own self-restraint) stopped you from accessing
shared_dir_writes: []        # any files you wrote/modified under ./code/ or ./data/ (should be empty)
notes: ""                    # one sentence on anything the verifier should know
```

Truth here is workshop data. Non-empty lists are valuable signal, not a reason to lie.
