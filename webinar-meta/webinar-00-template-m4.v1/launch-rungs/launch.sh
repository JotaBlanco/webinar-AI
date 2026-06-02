#!/usr/bin/env bash
# launch.sh — fan out parallel divergent subagents from manifest.yaml.
#
# Reads launch-rungs/manifest.yaml and starts one Claude Code session per
# subagent with isolated workdirs under launch-rungs/_sessions/<name>/.
# Each session inherits the m4.v1 substrate but writes only into its own
# models/<name>/ inside the shared template.
#
# Usage:
#   bash launch-rungs/launch.sh             # launch every subagent in manifest
#   bash launch-rungs/launch.sh rung-1-*    # filter by name glob
#
# This is a SKELETON shell driver. Adapt to your launch substrate
# (Claude Code CLI, agent-SDK loop, Quix runtime, whatever).

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MANIFEST="$ROOT/launch-rungs/manifest.yaml"
SESS_DIR="$ROOT/launch-rungs/_sessions"
mkdir -p "$SESS_DIR"

# Read subagent names from manifest. Requires yq or any YAML parser.
if ! command -v yq >/dev/null 2>&1; then
    echo "yq not found — install with 'brew install yq' or parse manifest.yaml another way." >&2
    exit 1
fi

NAMES=$(yq -r '.subagents[].name' "$MANIFEST")
FILTER="${1:-*}"

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

    echo "→ launching subagent: $NAME  (rung=$RUNG, budget=${BUDGET}min)"
    cat > "$SESS/PROMPT.md" <<EOF
# Subagent: $NAME

Rung: $RUNG.

You are one of N parallel subagents in a divergent-exploration fan-out. Your
job is to ship one candidate model at \`models/$NAME/\` and stop. Another
subagent is working a different rung at the same time; your role is to add
structural diversity to the cohort, not to beat them.

Constraints:
- Touch ONLY \`models/$NAME/\`. Do not modify other models/, MODELS.md,
  TREE.json, or EXPERIMENTS.md — the orchestrator runs \`iterate\` on your
  bundle and handles the registry.
- Budget: $BUDGET minutes wall clock.
- Use the same substrate (skills/, references/, _shared/) as the orchestrator.

Specific guidance for this rung:
$PROMPT

Read AGENTS.md, references/m4-cohort-findings.md, and any references named
in your prompt-hint above. When done, your candidate must:
1. Have \`models/$NAME/predict.py\` matching the operating contract
2. Have \`models/$NAME/notes.md\` declaring rung + parent + expected residual
3. Have one self-run of \`skills/score-model\` saved as \`models/$NAME/_local_score.txt\`
EOF

    # Replace this with your actual launch command:
    #   claude code --workdir "$ROOT" --prompt "$SESS/PROMPT.md" --budget "${BUDGET}m" &
    # The trailing & matters — these run in parallel.
    echo "  (dry-run: would launch Claude Code with $SESS/PROMPT.md, budget ${BUDGET}m)"
done

wait
echo "→ all subagents returned. Orchestrator: run iterate on each models/<subagent>/ and read MODELS.md."
