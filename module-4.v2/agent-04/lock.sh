#!/usr/bin/env bash
# lock.sh — chmod -w on a phase artifact. Called at the end of each phase.
# Shared between phases/1-research, phases/2-plan, phases/3-implement.
set -euo pipefail
TARGET="${1:?usage: lock.sh <path>}"
[ -f "$TARGET" ] || { echo "lock: $TARGET does not exist"; exit 1; }
chmod -w "$TARGET"
echo "→ locked $TARGET (chmod -w). pre-flight-final-model verifies this gate."
