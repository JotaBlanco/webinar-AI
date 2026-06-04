"""Standalone unit tests for _shared/gates.py.

Run with: python3 _shared/_test_gates.py

Pure-function tests — no filesystem outside tmp dirs, no template root, no
data segments. Exercises the four new m4.v1.01 gates that are wired into
both skills/iterate/ and skills/pre-flight-final-model/.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from gates import (  # noqa: E402
    check_bias_without_route_cv,
    check_iterate_history_min,
    check_parent_baseline_declared,
    check_report_cites_rejected,
    find_bias_violations,
)


# ---------- find_bias_violations -------------------------------------------

def test_no_bias_no_violation():
    assert find_bias_violations({
        "FORD_F_150_LIGHTNING_MK1": {"L": 3.7, "K": 0.004},
    }) == []


def test_bias_without_route_cv_violates():
    v = find_bias_violations({
        "FORD_F_150_LIGHTNING_MK1": {"L": 3.7, "K": 0.004, "bias_rad": -0.00411},
    })
    assert len(v) == 1
    assert "FORD_F_150_LIGHTNING_MK1.bias_rad" in v[0]


def test_bias_with_route_cv_passes():
    v = find_bias_violations({
        "FORD_F_150_LIGHTNING_MK1": {
            "L": 3.7, "K": 0.004, "bias_rad": -0.00411,
            "route_cv_sigma": 0.00031,
        },
    })
    assert v == []


def test_per_kpi_route_cv_also_passes():
    v = find_bias_violations({
        "FORD_F_150_LIGHTNING_MK1": {
            "bias": 0.001, "route_cv_sigma_yaw": 0.0002,
        },
    })
    assert v == []


def test_tiny_bias_below_floor_is_ignored():
    v = find_bias_violations({
        "FORD_F_150_LIGHTNING_MK1": {"bias_rad": 1e-9},
    })
    assert v == []


def test_nested_under_coeffs_key():
    v = find_bias_violations({
        "coeffs": {
            "HYUNDAI_IONIQ_5": {"delta_bias": 0.0011},
        },
    })
    assert len(v) == 1


def test_multiple_platforms_some_compliant():
    v = find_bias_violations({
        "FORD_F_150_LIGHTNING_MK1": {"bias_rad": -0.004},  # bad
        "HYUNDAI_IONIQ_5": {"bias_rad": 0.001, "route_cv_sigma": 0.0003},  # good
        "FORD_MUSTANG_MACH_E_MK1": {"L": 2.984},  # no bias
    })
    assert len(v) == 1
    assert "FORD_F_150_LIGHTNING_MK1" in v[0]


# ---------- check_bias_without_route_cv ------------------------------------

def test_check_bias_no_coeffs_json_passes():
    with tempfile.TemporaryDirectory() as tmp:
        ok, _ = check_bias_without_route_cv(Path(tmp) / "coeffs.json")
        assert ok


def test_check_bias_violation_fails():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "coeffs.json"
        p.write_text(json.dumps({
            "FORD_F_150_LIGHTNING_MK1": {"bias_rad": -0.004},
        }))
        ok, detail = check_bias_without_route_cv(p)
        assert not ok
        assert "route_cv_sigma" in detail
        assert "§6" in detail


def test_check_bias_unparseable_json_passes_with_note():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "coeffs.json"
        p.write_text("{not json")
        ok, detail = check_bias_without_route_cv(p)
        assert ok  # not our gate to fail
        assert "unparseable" in detail


# ---------- check_iterate_history_min --------------------------------------

ITERATE_ENTRY = """
### 2026-06-02T10:00:00Z — candidate-x
- Parent: v1  |  Rung: 0
- Dev CV: yaw 0.005800 ± 0.000200, CTE 55.2 ± 1.4
- vs V1: yaw -1.2%, CTE -2.8%
- Gate: pass — clean
- Residual: noise_floor
- Verdict: keep  →  next: try_residual_learner
"""


def test_iterate_history_missing_file_fails():
    with tempfile.TemporaryDirectory() as tmp:
        ok, _, count = check_iterate_history_min(
            Path(tmp) / "EXPERIMENTS.md", min_calls=4
        )
        assert not ok
        assert count == 0


def test_iterate_history_below_min_fails():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "EXPERIMENTS.md"
        p.write_text("# EXPERIMENTS.md\n" + ITERATE_ENTRY * 2)
        ok, detail, count = check_iterate_history_min(p, min_calls=4)
        assert not ok
        assert count == 2
        assert "agent-07" in detail


def test_iterate_history_meets_min_passes():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "EXPERIMENTS.md"
        p.write_text("# EXPERIMENTS.md\n" + ITERATE_ENTRY * 4)
        ok, _, count = check_iterate_history_min(p, min_calls=4)
        assert ok
        assert count == 4


def test_hand_written_entries_dont_count():
    """An entry must have all three iterate-written marker lines to count.
    A hand-written `## E03 — ...` block with `- Hypothesis:` / `- Result:`
    must not satisfy the gate — those are the lines exploration-discipline.md
    documents for manual entries."""
    hand_written = """
### 2026-06-02 — by hand
- Rung: 0
- Hypothesis: per-platform bias works on Lightning.
- Result (dev): yaw 0.0058; CTE 55.2.
"""
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "EXPERIMENTS.md"
        p.write_text("# EXPERIMENTS.md\n" + hand_written * 4)
        ok, _, count = check_iterate_history_min(p, min_calls=4)
        assert not ok
        assert count == 0


# ---------- check_report_cites_rejected ------------------------------------

def test_report_missing_fails():
    with tempfile.TemporaryDirectory() as tmp:
        ok, _ = check_report_cites_rejected(Path(tmp) / "REPORT.md")
        assert not ok


def test_report_no_rejected_section_fails():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "REPORT.md"
        p.write_text("# REPORT\n\n## What I shipped\n- final-model/\n")
        ok, detail = check_report_cites_rejected(p)
        assert not ok
        assert "## Candidates considered and rejected" in detail


def test_report_with_rejected_bullet_passes():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "REPORT.md"
        p.write_text(
            "# REPORT\n\n"
            "## Candidates considered and rejected\n\n"
            "- ridge-head: tried 7-feature ridge; shelved — dev-CV R² 0.04 below threshold.\n"
            "- gb-head: did not ship — ridge precondition not met.\n"
        )
        ok, _ = check_report_cites_rejected(p)
        assert ok


def test_report_with_placeholder_only_fails():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "REPORT.md"
        p.write_text(
            "# REPORT\n\n"
            "## Candidates considered and rejected\n\n"
            "| candidate | what it tried | verdict | one-line reason |\n"
            "|---|---|---|---|\n"
            "| <name> | <formulation> | shelved | <why it lost> |\n"
        )
        ok, _ = check_report_cites_rejected(p)
        # Has the "shelved" word but only in placeholder rows — the gate
        # filters those out.
        assert not ok


# ---------- check_parent_baseline_declared ---------------------------------

def test_plan_missing_fails():
    with tempfile.TemporaryDirectory() as tmp:
        ok, _ = check_parent_baseline_declared(Path(tmp) / "PLAN.md")
        assert not ok


def test_plan_no_section_fails():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "PLAN.md"
        p.write_text("# PLAN\n\n## Selected candidates\n\n- A\n- B\n")
        ok, detail = check_parent_baseline_declared(p)
        assert not ok
        assert "Parent baseline" in detail


def test_plan_with_filled_section_passes():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "PLAN.md"
        p.write_text(
            "# PLAN\n\n"
            "## Parent baseline\n\n"
            "- Baseline: V1\n"
            "- Evidence: V1 dev pooled yaw RMSE 0.00587 (m3.v3 cohort §1.7); "
            "V0 is 0.01293. V1 is the floor.\n"
            "- Floor we must clear: yaw 0.00587, CTE 56.81.\n"
        )
        ok, _ = check_parent_baseline_declared(p)
        assert ok


def test_plan_with_placeholder_only_fails():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "PLAN.md"
        p.write_text(
            "# PLAN\n\n"
            "## Parent baseline\n\n"
            "- Baseline: <V0 | V1 | fresh>\n"
            "- Evidence: <cite numbers>\n"
        )
        ok, detail = check_parent_baseline_declared(p)
        assert not ok
        assert "placeholders" in detail


# ---------- runner ----------------------------------------------------------

def main() -> int:
    tests = [v for k, v in globals().items() if k.startswith("test_")]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"  ok   {t.__name__}")
        except AssertionError as e:
            print(f"  FAIL {t.__name__}: {e}")
            failures += 1
        except Exception as e:
            print(f"  ERR  {t.__name__}: {type(e).__name__}: {e}")
            failures += 1
    print(f"\n{len(tests) - failures}/{len(tests)} passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
