#!/usr/bin/env bash
# S4 — Research → Plan → Implement loop launcher (TEMPLATE).
#
# Sequences three fresh Claude Code sessions, each with a narrowly-scoped
# context and the prior artifact mounted as the only project context.
# Each session writes to a timestamped run directory under runs/.
#
# Stub — implement before rehearsal. The three sessions are the load-bearing
# discipline of this scaffold: each MUST be fresh, each MUST read only the
# artifact(s) the proposal allows it to read.
set -euo pipefail

QUESTION_PATH="${1:-../../tasks/hello.md}"
RUN_DIR="runs/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RUN_DIR"

echo "S4-RPI run starting in $RUN_DIR"
echo "Question: $QUESTION_PATH"
echo

# ---- Phase 1: Research ----
echo "[1/3] Research phase — fresh context, reads project + skill + data."
cp templates/research.md "$RUN_DIR/research.md"
# TODO: spawn fresh Claude Code session scoped to repo root.
echo "      -> $RUN_DIR/research.md (review before continuing)"
read -r -p "      press Enter when research.md review is complete..."

# ---- Phase 2: Plan ----
echo "[2/3] Plan phase — fresh context, reads research.md + question only."
cp templates/plan.md "$RUN_DIR/plan.md"
# TODO: spawn fresh Claude Code session scoped to $RUN_DIR/ only.
echo "      -> $RUN_DIR/plan.md (lock before continuing)"
read -r -p "      press Enter when plan.md is reviewed and locked..."

# ---- Phase 3: Implement ----
echo "[3/3] Implement phase — fresh context, reads locked plan only."
# TODO: spawn fresh Claude Code session with $RUN_DIR/plan.md as the only input.
echo "      -> $RUN_DIR/implement-notes.md"

echo
echo "S4-RPI run complete. Three artifacts in $RUN_DIR — research, plan, implement."
