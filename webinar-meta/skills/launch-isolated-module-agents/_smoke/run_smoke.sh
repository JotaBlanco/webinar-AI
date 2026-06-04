#!/usr/bin/env bash
# Smoke test for launch-isolated-module-agents skill.
# Tests every script's happy path + the hook's deny path with synthetic payloads.
# Does NOT actually call the Agent tool — that requires a parent assistant.
#
# Run: bash _smoke/run_smoke.sh
# Exits 0 iff all checks pass; non-zero otherwise.

set -u

SKILL=$(cd "$(dirname "$0")/.." && pwd)
HOOK=$SKILL/hook-blocker.py
PRE=$SKILL/pre-flight-check.py
LAUNCH=$SKILL/launch-all.py
VERIFY=$SKILL/post-run-verify.py
ORCH=$SKILL/orchestrate.py
TMP=$(mktemp -d)
PASS=0
FAIL=0

ok()   { echo "  ✓ $1"; PASS=$((PASS+1)); }
fail() { echo "  ✗ $1"; FAIL=$((FAIL+1)); }

# Build a minimal fake "repo + angle" tree under $TMP.
FAKE_REPO=$TMP/fake-webinar-AI
ANGLE_ROOT=$FAKE_REPO/webinar-angle-Z
EXTERNAL_SECRET=$TMP/external-secret
mkdir -p "$FAKE_REPO/code" "$FAKE_REPO/data" "$FAKE_REPO/.claude" "$EXTERNAL_SECRET"
mkdir -p "$ANGLE_ROOT/_shared" "$ANGLE_ROOT/_observations"
echo "fake_code = 1" > "$FAKE_REPO/code/dummy.py"
echo "v_mps,delta_road_rad" > "$FAKE_REPO/data/dummy.csv"
echo "10.0,0.01" >> "$FAKE_REPO/data/dummy.csv"
echo "design-doc-leak" > "$ANGLE_ROOT/_shared/CHALLENGE.md"
echo "obs-leak" > "$ANGLE_ROOT/_observations/synth.md"
echo "EXTRA-FORBIDDEN-LEAK" > "$EXTERNAL_SECRET/kb.md"

for n in 1 2; do
  M=$ANGLE_ROOT/modulo-$n
  mkdir -p "$M/tasks" "$M/out"
  ln -s "$FAKE_REPO/code" "$M/code"
  ln -s "$FAKE_REPO/data" "$M/data"
  echo "dummy task" > "$M/tasks/challenge.md"
done

MANIFEST=$TMP/manifest.json
cat > "$MANIFEST" <<EOF
[
  {"module_name":"modulo-1","module_path":"$ANGLE_ROOT/modulo-1","harness_components_present":["Tools"],"task_relative_path":"tasks/challenge.md","time_budget_minutes":5},
  {"module_name":"modulo-2","module_path":"$ANGLE_ROOT/modulo-2","harness_components_present":["Tools","Memory"],"task_relative_path":"tasks/challenge.md","time_budget_minutes":5}
]
EOF

LAUNCH_CFG=$ANGLE_ROOT/.launch-config.json
cat > "$LAUNCH_CFG" <<EOF
{
  "angle_name": "webinar-angle-Z",
  "extra_forbidden": ["$EXTERNAL_SECRET"],
  "modules": $(cat "$MANIFEST")
}
EOF

echo "== 1. pre-flight PASSes on clean fake substrate =="
python3 "$PRE" "$MANIFEST" > /dev/null 2>&1 && ok "pre-flight exits 0" || fail "pre-flight should exit 0"

echo "== 2. pre-flight FAILs when a module path is missing =="
BAD_MANIFEST=$TMP/bad-manifest.json
sed "s|modulo-1|modulo-NOPE|g" "$MANIFEST" > "$BAD_MANIFEST"
python3 "$PRE" "$BAD_MANIFEST" > /dev/null 2>&1 && fail "pre-flight should fail" || ok "pre-flight non-zero on bad path"

echo "== 3. launch-all builds prompts + snapshot + invocations =="
python3 "$LAUNCH" "$MANIFEST" --extra-forbidden "$EXTERNAL_SECRET" > /dev/null 2>&1
LAUNCH_DIR=$(ls -dt "$ANGLE_ROOT"/_launch/*/ 2>/dev/null | head -1)
if [ -n "$LAUNCH_DIR" ] && [ -f "$LAUNCH_DIR/snapshot.txt" ] && [ -f "$LAUNCH_DIR/invocations.json" ]; then
  ok "launch-all produces snapshot.txt + invocations.json"
else
  fail "launch-all output missing"
fi
[ -f "$LAUNCH_DIR/modulo-1.prompt.md" ] && [ -f "$LAUNCH_DIR/modulo-2.prompt.md" ] && ok "one prompt per module" || fail "missing per-module prompts"
grep -q "ISOLATION_REPORT:" "$LAUNCH_DIR/modulo-1.prompt.md" && ok "ISOLATION_REPORT: tail present" || fail "ISOLATION_REPORT tail missing"
grep -q "modulo-2" "$LAUNCH_DIR/modulo-1.prompt.md" && ok "modulo-1 forbids modulo-2" || fail "modulo-1 missing sibling forbids"
grep -q "$EXTERNAL_SECRET" "$LAUNCH_DIR/modulo-1.prompt.md" && ok "extra-forbidden included in prompt" || fail "extra-forbidden missing from prompt"

echo "== 4. hook ALLOWS in-scope Read (module file) =="
P='{"session_id":"smoke","tool_name":"Read","cwd":"/tmp","tool_input":{"file_path":"'$ANGLE_ROOT'/modulo-1/tasks/challenge.md"}}'
echo "$P" | python3 "$HOOK" --repo-root "$FAKE_REPO" --extra-deny "$EXTERNAL_SECRET" > /dev/null 2>&1 && ok "hook allows module file" || fail "hook should allow module file"

echo "== 5. hook ALLOWS Read of shared code/ =="
P='{"session_id":"smoke","tool_name":"Read","cwd":"/tmp","tool_input":{"file_path":"'$FAKE_REPO'/code/dummy.py"}}'
echo "$P" | python3 "$HOOK" --repo-root "$FAKE_REPO" --extra-deny "$EXTERNAL_SECRET" > /dev/null 2>&1 && ok "hook allows shared code/" || fail "hook should allow code/"

echo "== 6. hook BLOCKS _shared/ (angle-meta leak) =="
P='{"session_id":"smoke","tool_name":"Read","cwd":"/tmp","tool_input":{"file_path":"'$ANGLE_ROOT'/_shared/CHALLENGE.md"}}'
echo "$P" | python3 "$HOOK" --repo-root "$FAKE_REPO" --extra-deny "$EXTERNAL_SECRET" > /dev/null 2>&1
RC=$?
[ "$RC" = "2" ] && ok "hook blocks _shared/ (exit 2)" || fail "hook returned $RC instead of 2"

echo "== 7. hook BLOCKS _observations/ =="
P='{"session_id":"smoke","tool_name":"Read","cwd":"/tmp","tool_input":{"file_path":"'$ANGLE_ROOT'/_observations/synth.md"}}'
echo "$P" | python3 "$HOOK" --repo-root "$FAKE_REPO" --extra-deny "$EXTERNAL_SECRET" > /dev/null 2>&1
RC=$?
[ "$RC" = "2" ] && ok "hook blocks _observations/ (exit 2)" || fail "hook returned $RC instead of 2"

echo "== 8. hook BLOCKS --extra-deny path =="
P='{"session_id":"smoke","tool_name":"Read","cwd":"/tmp","tool_input":{"file_path":"'$EXTERNAL_SECRET'/kb.md"}}'
echo "$P" | python3 "$HOOK" --repo-root "$FAKE_REPO" --extra-deny "$EXTERNAL_SECRET" > /dev/null 2>&1
RC=$?
[ "$RC" = "2" ] && ok "hook blocks --extra-deny path (exit 2)" || fail "hook returned $RC instead of 2"

echo "== 9. hook BLOCKS Bash that reads forbidden path =="
P='{"session_id":"smoke","tool_name":"Bash","cwd":"/tmp","tool_input":{"command":"cat '$ANGLE_ROOT'/_shared/CHALLENGE.md"}}'
echo "$P" | python3 "$HOOK" --repo-root "$FAKE_REPO" --extra-deny "$EXTERNAL_SECRET" > /dev/null 2>&1
RC=$?
[ "$RC" = "2" ] && ok "hook blocks forbidden Bash (exit 2)" || fail "hook returned $RC instead of 2"

echo "== 10. hook LOGS denied attempts =="
LOG=$FAKE_REPO/.claude/blocked-attempts.log
[ -f "$LOG" ] && [ "$(wc -l < "$LOG" | tr -d ' ')" -ge "3" ] && ok "blocked-attempts.log captured ≥3 entries" || fail "log missing or empty"

echo "== 11. orchestrate.py runs end-to-end =="
python3 "$ORCH" "$ANGLE_ROOT" > "$TMP/orch.out" 2>&1
RC=$?
if [ "$RC" = "0" ] && grep -q "BEGIN_INVOCATIONS" "$TMP/orch.out" && grep -q "END_INVOCATIONS" "$TMP/orch.out"; then
  ok "orchestrate prints invocations block"
else
  fail "orchestrate failed (rc=$RC)"
  cat "$TMP/orch.out"
fi

echo "== 12. orchestrate --verify produces structured output =="
python3 "$ORCH" "$ANGLE_ROOT" --verify > "$TMP/verify.out" 2>&1
if grep -q "V1 self-report" "$TMP/verify.out" && grep -q "V2 fs-diff" "$TMP/verify.out" && grep -q "V3 hook log" "$TMP/verify.out"; then
  ok "orchestrate --verify produces all three views"
else
  fail "orchestrate --verify output missing views"
  cat "$TMP/verify.out"
fi

rm -rf "$TMP"

echo
echo "passed: $PASS, failed: $FAIL"
[ "$FAIL" = "0" ] && exit 0 || exit 1
