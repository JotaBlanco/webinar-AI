#!/usr/bin/env bash
# lock.sh — chmod -w on an RPI artifact. Called at end of each phase.
set -euo pipefail
TARGET="${1:?usage: lock.sh <path>}"
[ -f "$TARGET" ] || { echo "lock: $TARGET does not exist"; exit 1; }
chmod -w "$TARGET"
echo "→ locked $TARGET (chmod -w). pre-flight-final-model verifies this gate."
