#!/usr/bin/env bash
# launch.sh — fan out parallel divergent subagents from manifest.yaml.
#
# Spawns one Claude Code session per subagent in true OS-level parallel via
# the `claude` CLI. Each session runs in the SAME template root (so they
# share skills/, references/, _shared/, the symlinked data/ and code/), but
# is constrained by its generated PROMPT.md to write only into its own
# models/<name>/.
#
# Usage:
#   bash launch-rungs/launch.sh             # launch every subagent in manifest
#   bash launch-rungs/launch.sh rung-1-*    # filter by name glob
#   bash launch-rungs/launch.sh --dry       # generate PROMPT.md files but do not spawn
#
# Requirements:
#   - claude CLI on PATH (https://docs.claude.com/claude-code)
#   - yq on PATH (brew install yq) for manifest parsing
#
# If you're inside Claude Code already (rather than driving from a shell),
# use launch-rungs/orchestrate.md instead — same fan-out via the in-process
# Task tool.

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="$ROOT/launch-rungs/manifest.yaml"
SESS_DIR="$ROOT/launch-rungs/_sessions"
mkdir -p "$SESS_DIR"

DRY=0
FILTER="*"
for arg in "$@"; do
    case "$arg" in
        --dry) DRY=1 ;;
        *) FILTER="$arg" ;;
    esac
done

command -v yq >/dev/null 2>&1 || { echo "yq not found — install with 'brew install yq'." >&2; exit 1; }
if [ "$DRY" -eq 0 ]; then
    command -v claude >/dev/null 2>&1 || {
        echo "claude CLI not found. Use --dry to generate PROMPT.md files only," >&2
        echo "or use launch-rungs/orchestrate.md from inside a Claude Code session." >&2
        exit 1
    }
fi

NAMES=$(yq -r '.subagents[].name' "$MANIFEST")
PIDS=()

for NAME in $NAMES; do
    case "$NAME" in
        $FILTER) ;;
        *) continue ;;
    esac
    SESS="$SESS_DIR/$NAME"
    mkdir -p "$SESS"
    PROMPT=$(yq -r ".subagents[] | select(.name == \"$NAME\") | .prompt_hint" "$MANIFEST")
    BUDGET=$(yq -r ".subagents[] | select(.name == \"$NAME\") | .budget_minutes" "$MANIFEST")
    RUNG=$(yq -r ".subagents[] | select(.name == \"$NAME\") | .rung" "$MANIFEST")

    cat > "$SESS/PROMPT.md" <<EOF
# Subagent: $NAME — Rung $RUNG

You are one of N parallel subagents in a divergent-exploration fan-out. Your
job is to ship one candidate model at \`models/$NAME/\` and stop. Other
subagents are working different rungs in parallel; your role is structural
diversity, not winning against them.

Hard constraints:
- Touch ONLY \`models/$NAME/\` (create the dir, write predict.py + notes.md).
  Do not modify other models/, MODELS.md, TREE.json, EXPERIMENTS.md, or
  final-model/. The orchestrator runs \`skills/iterate/\` on your bundle when
  you return and handles all registry updates.
- Budget: $BUDGET minutes wall clock.
- Read AGENTS.md, references/m4-cohort-findings.md, references/closing-the-loop.md
  before starting. Load the dynamics-formulations.md or anti-patterns.md
  references only if they're cited in your rung's prompt-hint below.
- Your notes.md must declare: rung, parent (v1 or another models/ name),
  expected residual character, and a \`## What this differs from\` section
  naming what other rungs/approaches you ruled out (the orchestrator's
  iterate gate enforces this).

Specific guidance for your rung:

$PROMPT

When done:
1. \`models/$NAME/predict.py\` matches the operating contract.
2. \`models/$NAME/notes.md\` is filled in (including \`## What this differs from\`).
3. One self-run of \`skills/score-model\` saved as \`models/$NAME/_local_score.txt\`.
4. Exit.
EOF

    if [ "$DRY" -eq 1 ]; then
        echo "→ [dry] $NAME — prompt written to $SESS/PROMPT.md"
        continue
    fi

    echo "→ launching subagent: $NAME  (rung=$RUNG, budget=${BUDGET}min)"
    # --print runs non-interactive; --output-format stream-json captures the
    # session log for the orchestrator to inspect. Stderr goes to a per-session
    # log file. Wall-clock budget is enforced by `timeout`.
    (
        timeout "${BUDGET}m" claude \
            --print \
            --output-format stream-json \
            --append-system-prompt "$(cat "$SESS/PROMPT.md")" \
            --add-dir "$ROOT" \
            > "$SESS/session.jsonl" \
            2> "$SESS/stderr.log" \
        || echo "[subagent $NAME exited with status $? at $(date -Is)]" >> "$SESS/stderr.log"
    ) &
    PIDS+=("$!")
done

if [ "$DRY" -eq 1 ]; then
    echo "→ dry run complete. Inspect prompts under $SESS_DIR/. Re-run without --dry to launch."
    exit 0
fi

echo "→ ${#PIDS[@]} subagents running in parallel. Waiting…"
for pid in "${PIDS[@]}"; do
    wait "$pid" || true
done

echo
echo "→ all subagents returned. Orchestrator next steps:"
echo "    1. Inspect $SESS_DIR/<name>/session.jsonl for each return"
echo "    2. For each returned bundle, run from template root:"
echo "         python -m skills.iterate.iterate models/<name>"
echo "    3. Read MODELS.md + TREE.json — pick the dev-CV leader"
