#!/usr/bin/env bash
# _smoke_template.sh — end-to-end template solidity check.
#
# Runs every smoke / unit-test / audit / lock-script path in the template and
# reports a single pass/fail summary. No real `data/` needed; everything here
# is synthetic or self-contained.
#
# Exit 0 if everything green; exit 1 otherwise.

set -uo pipefail
cd "$(dirname "$0")"
ROOT="$(pwd)"

pass=0
fail=0
failures=()

run() {
    local name="$1"; shift
    local out
    if out=$("$@" 2>&1); then
        printf "  [ok  ] %s\n" "$name"
        pass=$((pass + 1))
    else
        printf "  [FAIL] %s\n" "$name"
        printf "         (last 3 lines of output:)\n"
        printf '%s\n' "$out" | tail -3 | sed 's/^/         > /'
        fail=$((fail + 1))
        failures+=("$name")
    fi
}

run_expect_fail() {
    # For commands where exit != 0 is the success condition (e.g. lock.sh
    # refusing a bad PLAN.md). Inverts the success check.
    local name="$1"; shift
    if "$@" >/dev/null 2>&1; then
        printf "  [FAIL] %s  (expected non-zero exit, got 0)\n" "$name"
        fail=$((fail + 1))
        failures+=("$name")
    else
        printf "  [ok  ] %s\n" "$name"
        pass=$((pass + 1))
    fi
}

echo "============================================================"
echo "  m4.v1.01 template solidity smoke"
echo "  root: $ROOT"
echo "============================================================"

# ---- 1. Required top-level files / dirs ----------------------------------
echo
echo "[1/8] Required top-level files + dirs"
for f in AGENTS.md README.md MODELS.md TREE.json EXPERIMENTS.md REPORT.md.template \
         pyproject.toml ; do
    if [ -f "$f" ]; then printf "  [ok  ] %s exists\n" "$f"; pass=$((pass+1))
    else printf "  [FAIL] %s missing\n" "$f"; fail=$((fail+1)); failures+=("$f missing"); fi
done
for d in skills references _shared rpi launch-rungs physics-catalog code data; do
    if [ -d "$d" ]; then printf "  [ok  ] %s/ exists\n" "$d"; pass=$((pass+1))
    else printf "  [FAIL] %s/ missing\n" "$d"; fail=$((fail+1)); failures+=("$d missing"); fi
done

# ---- 2. Python imports (every .py imports without syntax error) ---------
echo
echo "[2/8] Python import sanity (no syntax errors anywhere)"
python_files=$(find skills _shared physics-catalog code -type f -name "*.py" \
               -not -path "*__pycache__*" 2>/dev/null)
python_fail=0
for pyfile in $python_files; do
    if ! python3 -c "
import importlib.util, sys
spec = importlib.util.spec_from_file_location('_smoke_load', '$pyfile')
mod = importlib.util.module_from_spec(spec)
sys.modules['_smoke_load'] = mod
spec.loader.exec_module(mod)
" >/dev/null 2>&1; then
        # Only flag genuine SyntaxErrors. Many files raise at import-time because
        # they expect to be loaded from a particular cwd or with the template
        # tree intact (e.g. data symlinks). We test those separately below.
        if python3 -c "import ast; ast.parse(open('$pyfile').read())" >/dev/null 2>&1; then
            : # parses fine; runtime import issue is fine here
        else
            printf "  [FAIL] %s — SyntaxError\n" "$pyfile"
            python_fail=$((python_fail + 1))
        fi
    fi
done
if [ "$python_fail" -eq 0 ]; then
    nf=$(echo "$python_files" | wc -l | tr -d ' ')
    printf "  [ok  ] all %s Python files parse without SyntaxError\n" "$nf"
    pass=$((pass + 1))
else
    fail=$((fail + python_fail))
    failures+=("python_syntax (${python_fail} files)")
fi

# ---- 3. v1.01 gate unit tests --------------------------------------------
echo
echo "[3/8] v1.01 gate unit tests (_shared/_test_gates.py)"
run "_shared/_test_gates.py (22 tests)" python3 _shared/_test_gates.py

# ---- 4. Each catalog model smoke (8 models) ------------------------------
echo
echo "[4/8] Per-model smoke (8 models)"
for m in dst_lin dst_nl dst_regime dst_relax dst_load \
         dst_twin_track dst_combined_slip dst_steer_compliance; do
    run "$m/smoke.py" python3 "physics-catalog/$m/smoke.py"
done

# ---- 5. Catalog audit (40 cells) -----------------------------------------
echo
echo "[5/8] physics-catalog/_audit.py (40 cells)"
run "_audit.py (synthetic)" python3 physics-catalog/_audit.py

# ---- 6. lock.sh PLAN.md guardrail ----------------------------------------
echo
echo "[6/8] lock.sh PLAN.md guard (m4.v1.01 parent-baseline check)"
tmp=$(mktemp -d)
trap "rm -rf '$tmp'" EXIT

# 6a. lock.sh refuses PLAN.md with no parent-baseline section.
cat > "$tmp/PLAN.md" <<'EOF'
# PLAN
## Selected candidates
- A
EOF
run_expect_fail "lock.sh refuses PLAN.md without parent-baseline" \
    bash "$ROOT/rpi/lock.sh" "$tmp/PLAN.md"

# 6b. lock.sh refuses placeholder-only parent-baseline.
cat > "$tmp/PLAN.md" <<'EOF'
# PLAN
## Parent baseline
- Baseline: <V0 | V1 | fresh>
- Evidence: <cite numbers>
EOF
run_expect_fail "lock.sh refuses placeholder-only PLAN.md" \
    bash "$ROOT/rpi/lock.sh" "$tmp/PLAN.md"

# 6c. lock.sh accepts a properly-filled PLAN.md.
cat > "$tmp/PLAN.md" <<'EOF'
# PLAN
## Parent baseline
- Baseline: V1
- Evidence: V1 dev pooled yaw RMSE 0.00587; V0 is 0.01293.
- Floor: yaw 0.00587, CTE 56.81.
## Selected candidates
- A
EOF
run "lock.sh accepts well-formed PLAN.md" \
    bash "$ROOT/rpi/lock.sh" "$tmp/PLAN.md"

# ---- 6b. MODELS.md documented threshold matches preflight constant -------
# Catches the m4.v1 → v1.01 drift where the code bumped MIN_MODELS_MD_CANDIDATES
# from 4 → 6 but MODELS.md still said "≥4 entries total".
echo
echo "[6b] MODELS.md thresholds match preflight constants"
preflight_min=$(python3 -c "
import re, sys
text = open('skills/pre-flight-final-model/preflight.py').read()
m = re.search(r'MIN_MODELS_MD_CANDIDATES\s*=\s*(\d+)', text)
print(m.group(1) if m else 'MISSING')
")
preflight_history=$(python3 -c "
import re, sys
text = open('skills/pre-flight-final-model/preflight.py').read()
m = re.search(r'MIN_ITERATE_HISTORY\s*=\s*(\d+)', text)
print(m.group(1) if m else 'MISSING')
")
models_md_text=$(cat MODELS.md)
if echo "$models_md_text" | grep -qE "≥${preflight_min} entries total"; then
    printf "  [ok  ] MODELS.md cites '≥%s entries total' matching preflight\n" "$preflight_min"
    pass=$((pass + 1))
else
    printf "  [FAIL] MODELS.md does not cite '≥%s entries total' — preflight says %s\n" \
           "$preflight_min" "$preflight_min"
    fail=$((fail + 1)); failures+=("MODELS.md min-entries threshold drift")
fi
if echo "$models_md_text" | grep -qE "≥${preflight_history} entries written by"; then
    printf "  [ok  ] MODELS.md cites '≥%s entries written by skills/iterate' matching preflight\n" "$preflight_history"
    pass=$((pass + 1))
else
    printf "  [FAIL] MODELS.md does not cite '≥%s entries written by skills/iterate' — preflight says %s\n" \
           "$preflight_history" "$preflight_history"
    fail=$((fail + 1)); failures+=("MODELS.md iterate-history threshold drift")
fi

# Also: PLAN.md.template's default candidate count must match what run-plan.sh
# prompts the spawned session to do. m4.v1.01 default is 3.
plan_default=$(grep -cE "default 3|default of 3|THREE candidates|Pick THREE" rpi/run-plan.sh)
plan_tpl_default=$(grep -cE "default 3|default of 3|Pick THREE" rpi/templates/PLAN.md.template)
if [ "$plan_default" -ge 1 ] && [ "$plan_tpl_default" -ge 1 ]; then
    printf "  [ok  ] run-plan.sh and PLAN.md.template both say default = 3 candidates\n"
    pass=$((pass + 1))
else
    printf "  [FAIL] run-plan.sh / PLAN.md.template default-candidate count drift\n"
    fail=$((fail + 1)); failures+=("PLAN candidate default drift")
fi

# Also: any "Why three candidates" reference in run-plan.sh is stale (template
# uses "Why only two candidates"). Catch this dead-link drift.
if grep -q "Why three candidates" rpi/run-plan.sh; then
    printf "  [FAIL] run-plan.sh references stale section 'Why three candidates'\n"
    fail=$((fail + 1)); failures+=("run-plan.sh stale section name")
else
    printf "  [ok  ] run-plan.sh has no stale 'Why three candidates' references\n"
    pass=$((pass + 1))
fi

# ---- 7. Reference docs exist + non-trivial -------------------------------
echo
echo "[7/8] Reference docs"
for ref in references/m4-cohort-findings.md references/physics-menu.md \
           references/build-your-own-model.md references/closing-the-loop.md \
           references/dynamics-formulations.md references/exploration-discipline.md \
           references/approach-menu.md references/anti-patterns.md \
           references/two-kpi-tradeoff.md references/ceiling-moves.md; do
    if [ -f "$ref" ] && [ "$(wc -c < "$ref")" -gt 500 ]; then
        printf "  [ok  ] %s (%s bytes)\n" "$ref" "$(wc -c < "$ref" | tr -d ' ')"
        pass=$((pass + 1))
    else
        printf "  [FAIL] %s missing or < 500 bytes\n" "$ref"
        fail=$((fail + 1)); failures+=("$ref")
    fi
done

# ---- 8. launch-rungs manifest parses + catalog-bound slots ---------------
echo
echo "[8/8] launch-rungs manifest + catalog binding"
manifest_report=$(python3 - <<'PY'
import json, sys
try:
    import yaml
except ImportError:
    print(json.dumps({"error": "PyYAML not installed (pip install pyyaml)"}))
    sys.exit(0)

import os
from pathlib import Path
root = Path(os.environ.get("MANIFEST_ROOT", "."))
with open(root / "launch-rungs/manifest.yaml") as f:
    m = yaml.safe_load(f)
subs = m.get("subagents") or []
names = [s.get("name") for s in subs]
bound = [s for s in subs if (s.get("catalog_starter") or "").startswith("physics-catalog/")]
missing_paths = [s["catalog_starter"] for s in bound
                 if not (root / s["catalog_starter"]).is_dir()]
orchestrator_budget = (m.get("orchestrator") or {}).get("budget_minutes")
print(json.dumps({
    "n_subagents": len(subs),
    "names": names,
    "n_bound_to_catalog": len(bound),
    "missing_paths": missing_paths,
    "orchestrator_budget_min": orchestrator_budget,
}))
PY
)
err=$(echo "$manifest_report" | python3 -c "import json,sys; d=json.loads(sys.stdin.read()); print(d.get('error',''))")
if [ -n "$err" ]; then
    printf "  [skip] %s\n" "$err"
else
    n_subagents=$(echo "$manifest_report" | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['n_subagents'])")
    n_bound=$(echo "$manifest_report" | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['n_bound_to_catalog'])")
    missing_count=$(echo "$manifest_report" | python3 -c "import json,sys; print(len(json.loads(sys.stdin.read())['missing_paths']))")
    orch_budget=$(echo "$manifest_report" | python3 -c "import json,sys; print(json.loads(sys.stdin.read())['orchestrator_budget_min'])")

    if [ "$n_subagents" -ge 6 ]; then
        printf "  [ok  ] manifest declares %s subagents (>= 6)\n" "$n_subagents"
        pass=$((pass + 1))
    else
        printf "  [FAIL] manifest declares only %s subagents (want >= 6)\n" "$n_subagents"
        fail=$((fail + 1)); failures+=("manifest subagent count")
    fi

    if [ "$n_bound" -ge 5 ]; then
        printf "  [ok  ] %s subagents bound to physics-catalog starters (>= 5)\n" "$n_bound"
        pass=$((pass + 1))
    else
        printf "  [FAIL] only %s subagents bound to catalog (want >= 5)\n" "$n_bound"
        fail=$((fail + 1)); failures+=("manifest catalog binding count")
    fi

    if [ "$missing_count" -eq 0 ]; then
        printf "  [ok  ] all manifest catalog_starter paths exist on disk\n"
        pass=$((pass + 1))
    else
        printf "  [FAIL] %s manifest catalog_starter path(s) do not exist on disk\n" "$missing_count"
        fail=$((fail + 1)); failures+=("manifest starter paths")
    fi

    if [ "$orch_budget" = "90" ]; then
        printf "  [ok  ] orchestrator budget = 90 min (m4.v1.01 default)\n"
        pass=$((pass + 1))
    else
        printf "  [FAIL] orchestrator budget = %s (want 90 in m4.v1.01)\n" "$orch_budget"
        fail=$((fail + 1)); failures+=("orchestrator budget")
    fi
fi

# ---- Summary -------------------------------------------------------------
echo
echo "============================================================"
echo "  SUMMARY"
echo "============================================================"
total=$((pass + fail))
printf "  %d / %d checks passed\n" "$pass" "$total"
if [ "$fail" -eq 0 ]; then
    echo
    echo "  ✓ Template is solid."
    exit 0
else
    echo
    echo "  ✗ ${fail} failure(s):"
    for f in "${failures[@]}"; do
        printf "    - %s\n" "$f"
    done
    exit 1
fi
