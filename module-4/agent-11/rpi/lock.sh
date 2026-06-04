#!/usr/bin/env bash
# lock.sh — chmod -w on an RPI artifact. Called at end of each phase.
#
# m4.v1.01 — when locking PLAN.md, also verify that the `## Parent baseline`
# section is present AND non-placeholder. This is the mechanical guard for the
# m4.v1 agent-10 failure mode (built on V0; -17 pp behind the cohort).
set -euo pipefail
TARGET="${1:?usage: lock.sh <path>}"
[ -f "$TARGET" ] || { echo "lock: $TARGET does not exist"; exit 1; }

BASENAME=$(basename "$TARGET")
if [ "$BASENAME" = "PLAN.md" ]; then
    if ! grep -q "^## Parent baseline" "$TARGET"; then
        echo "lock: PLAN.md is missing the '## Parent baseline' section." >&2
        echo "      Add it (V0 | V1 | fresh + one line of evidence) and re-run lock.sh." >&2
        echo "      Motivating failure: m4.v1 agent-10 built on V0; -17 pp behind cohort." >&2
        exit 1
    fi
    # Extract the body of the Parent baseline section. Crude but enough for a
    # placeholder-only detector. We temporarily disable pipefail because the
    # grep -v chain returns non-zero when *all* lines are filtered out (which
    # is exactly the placeholder case we want to detect, not error on).
    SECTION=$(awk '/^## Parent baseline/{flag=1; next} /^## /{flag=0} flag' "$TARGET")
    set +o pipefail
    MEANINGFUL=$(printf '%s\n' "$SECTION" \
        | grep -vE '^[[:space:]]*$' \
        | grep -vE '^[[:space:]]*>' \
        | grep -vE '^[[:space:]]*<!--' \
        | grep -vE '<[A-Za-z0-9_| .,-]+>' \
        | wc -l \
        | tr -d ' ')
    set -o pipefail
    if [ "$MEANINGFUL" -lt 2 ]; then
        echo "lock: PLAN.md '## Parent baseline' section is present but appears" >&2
        echo "      to contain only placeholders / blockquote guidance." >&2
        echo "      Fill in the choice (V0/V1/fresh) AND one line of evidence." >&2
        exit 1
    fi
fi

chmod -w "$TARGET"
echo "→ locked $TARGET (chmod -w). pre-flight-final-model verifies this gate."
