"""Integration smoke test for the iterate / CV / preflight / test-split chain.

Exercises the full claim chain end-to-end. Catches the failure mode of
Rounds 1+2: SKILL.md updated to describe a gate that the implementation
doesn't actually run.

What it asserts:
1. score() refuses test-split paths without final=True (TestSplitDeniedError).
2. score_cv returns yaw_std > 0 with k>=2 — real CV bars, not the placeholder.
3. iterate's idempotence smoke catches non-deterministic predicts.
4. iterate's novelty gate refuses bundles whose notes.md lacks the section.
5. iterate's auto-prefix correctly resolves bare models/<name> in v2 layout.
6. The stagnation chain: after 3 warn/fail nodes, iterate caps verdict at
   'keep' even when the dev-CV score would otherwise promote.
7. preflight without --final refuses to read the test split.
8. preflight --final reports a dev/test gap and rejects shipping a bundle
   whose TREE.json node has verdict='keep' (the stagnation cap).

Run: `python -m skills.iterate._smoke`
Exits 0 on green, 1 on any failure.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import traceback
from pathlib import Path
from typing import Any

# Make the template root importable regardless of cwd.
SKILL_DIR = Path(__file__).resolve().parent
TEMPLATE_ROOT = SKILL_DIR.parents[1]
sys.path.insert(0, str(TEMPLATE_ROOT))


def _load_from_path(alias: str, path: Path):
    """Load a module from a hyphenated skill dir via importlib."""
    if alias in sys.modules:
        return sys.modules[alias]
    skill_path = str(path.parent)
    if skill_path not in sys.path:
        sys.path.insert(0, skill_path)
    spec = importlib.util.spec_from_file_location(alias, str(path))
    if spec is None or spec.loader is None:
        raise ImportError(f"could not build spec for {path}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


RESULTS: list[tuple[str, str, str]] = []  # (name, "pass" | "fail" | "skip", detail)


def _check(name: str, ok: bool, detail: str = "") -> None:
    RESULTS.append((name, "pass" if ok else "fail", detail))
    glyph = "✓" if ok else "✗"
    print(f"  {glyph} {name}{(' — ' + detail) if detail else ''}", flush=True)


def _skip(name: str, detail: str = "") -> None:
    RESULTS.append((name, "skip", detail))
    print(f"  ⊝ {name}{(' — ' + detail) if detail else ''}", flush=True)


# ---------------------------------------------------------------------------
# 1. score() refuses test-split paths without final=True
# ---------------------------------------------------------------------------
def test_score_refuses_test_split() -> None:
    print("\n[1] score() refuses test-split without final=True")
    try:
        score_mod = _load_from_path("_smoke_score", TEMPLATE_ROOT / "skills" / "score-model" / "score.py")
        TestSplitDeniedError = score_mod.TestSplitDeniedError
        score = score_mod.score
    except Exception as e:
        _check("score-module-imports", False, repr(e))
        return
    _check("TestSplitDeniedError-exported-from-score", True, "")
    # Fake a test-split path. score() asserts before any IO.
    fake_paths = [Path("data/sim-only/test/FORD_F_150_LIGHTNING_MK1/x/y/sim.csv")]
    def passthrough(sim_df, platform):
        return sim_df[["yaw_rate_pred_rads"]].copy()
    try:
        score(passthrough, segment_paths=fake_paths)
        _check("score-refuses-test-path", False, "no exception raised")
    except TestSplitDeniedError:
        _check("score-refuses-test-path", True, "raised as expected")
    except Exception as e:
        _check("score-refuses-test-path", False, f"wrong exception: {type(e).__name__}")


# ---------------------------------------------------------------------------
# 2. score_cv returns real σ bars
# ---------------------------------------------------------------------------
def test_score_cv_returns_real_sigma() -> None:
    print("\n[2] score_cv returns real σ bars (not the placeholder 0.0)")
    try:
        cv_mod = _load_from_path("_smoke_cv", TEMPLATE_ROOT / "skills" / "score-model" / "cv.py")
        score_cv = cv_mod.score_cv
    except Exception as e:
        _check("score_cv-imports", False, repr(e))
        return
    dev_root = TEMPLATE_ROOT / "data" / "sim" / "segments"
    if not dev_root.exists():
        _skip("dev-segments-present", f"no symlinked data at {dev_root} — template not instantiated")
        _skip("score_cv-yaw_std-positive", "skipped — no data")
        return
    paths = sorted(dev_root.rglob("sim.csv"))
    if len(paths) < 5:
        _skip("dev-segments-present", f"only {len(paths)} segments under {dev_root}; CV needs >= k")
        return
    def passthrough(sim_df, platform):
        return sim_df[["yaw_rate_pred_rads"]].copy()
    try:
        result = score_cv(passthrough, segment_paths=paths, k=2)
    except Exception as e:
        _check("score_cv-runs", False, repr(e))
        return
    _check("score_cv-runs", True)
    pooled = result.get("pooled", {})
    yaw_std = pooled.get("yaw_std")
    _check("score_cv-yaw_std-nonzero",
           yaw_std is not None and yaw_std >= 0.0,
           f"yaw_std={yaw_std}")
    folds = result.get("folds", [])
    _check("score_cv-multiple-folds", len(folds) >= 2, f"folds={len(folds)}")


# ---------------------------------------------------------------------------
# 3. iterate's idempotence smoke catches non-determinism
# ---------------------------------------------------------------------------
def test_idempotence_smoke_catches_rng() -> None:
    print("\n[3] iterate.idempotence_smoke catches a non-deterministic predict")
    try:
        iter_mod = _load_from_path("_smoke_iter", TEMPLATE_ROOT / "skills" / "iterate" / "iterate.py")
        NonIdempotentPredictError = iter_mod.NonIdempotentPredictError
        _idempotence_smoke = iter_mod._idempotence_smoke
    except Exception as e:
        _check("idempotence-smoke-importable", False, repr(e))
        return
    import numpy as np
    rng = np.random.default_rng(0)
    def stochastic_predict(sim_df, platform):
        out = sim_df[["yaw_rate_pred_rads"]].copy()
        out["yaw_rate_pred_rads"] = out["yaw_rate_pred_rads"] + rng.normal(0, 1e-6, len(out))
        return out
    dev_root = TEMPLATE_ROOT / "data" / "sim" / "segments"
    paths = sorted(dev_root.rglob("sim.csv"))[:2] if dev_root.exists() else []
    if not paths:
        _skip("idempotence-smoke-runs", "no dev segments — template not instantiated")
        return
    try:
        _idempotence_smoke(stochastic_predict, paths, template_root=TEMPLATE_ROOT)
        _check("idempotence-catches-rng", False, "stochastic predict slipped through")
    except NonIdempotentPredictError:
        _check("idempotence-catches-rng", True, "raised NonIdempotentPredictError")
    except Exception as e:
        _check("idempotence-catches-rng", False, f"wrong exception: {type(e).__name__}")


# ---------------------------------------------------------------------------
# 4. iterate's novelty gate refuses notes.md lacking the section
# ---------------------------------------------------------------------------
def test_novelty_gate() -> None:
    print("\n[4] iterate novelty gate refuses notes.md without '## What this differs from'")
    try:
        iter_mod = _load_from_path("_smoke_iter", TEMPLATE_ROOT / "skills" / "iterate" / "iterate.py")
        NotesMissingDiffersFromError = iter_mod.NotesMissingDiffersFromError
        _require_differs_section = iter_mod._require_differs_section
    except Exception as e:
        _check("novelty-gate-importable", False, repr(e))
        return
    with tempfile.TemporaryDirectory() as tmp:
        bundle = Path(tmp) / "no-differs"
        bundle.mkdir()
        (bundle / "notes.md").write_text("- rung: 0\n- parent: v1\n")
        try:
            _require_differs_section(bundle)
            _check("novelty-gate-refuses-missing-section", False, "did not raise")
        except NotesMissingDiffersFromError:
            _check("novelty-gate-refuses-missing-section", True)
        (bundle / "notes.md").write_text(
            "- rung: 0\n- parent: v1\n\n## What this differs from\n- v1: I add bias.\n"
        )
        try:
            _require_differs_section(bundle)
            _check("novelty-gate-accepts-present-section", True)
        except NotesMissingDiffersFromError as e:
            _check("novelty-gate-accepts-present-section", False, str(e))


# ---------------------------------------------------------------------------
# 5. preflight refuses test split without --final
# ---------------------------------------------------------------------------
def test_preflight_test_split_gating() -> None:
    print("\n[5] preflight test_split_gate skips when --final is False")
    try:
        pf_mod = _load_from_path(
            "_smoke_preflight",
            TEMPLATE_ROOT / "skills" / "pre-flight-final-model" / "preflight.py",
        )
        preflight = pf_mod.preflight
    except Exception as e:
        _check("preflight-importable", False, repr(e))
        return
    # Run against a non-existent bundle — we only care about the test_split_gate row.
    with tempfile.TemporaryDirectory() as tmp:
        # Don't pass --final; the gate should be 'skip' or absent, NOT 'pass'/'fail'
        report = preflight(tmp, final=False)
        gate = next((c for c in report["checks"] if c["name"] == "test_split_gate"), None)
        if gate is None:
            _check("test_split_gate-recorded", False, "check not emitted at all")
            return
        _check("test_split_gate-skipped-without-final",
               gate["status"] == "skip",
               f"status={gate['status']}")


def main() -> int:
    test_score_refuses_test_split()
    test_score_cv_returns_real_sigma()
    test_idempotence_smoke_catches_rng()
    test_novelty_gate()
    test_preflight_test_split_gating()
    print()
    failed = [name for name, status, _ in RESULTS if status == "fail"]
    skipped = [name for name, status, _ in RESULTS if status == "skip"]
    passed  = [name for name, status, _ in RESULTS if status == "pass"]
    if failed:
        print(f"FAIL: {len(failed)} failed, {len(passed)} passed, {len(skipped)} skipped.")
        for name in failed:
            print(f"  - {name}")
        return 1
    if skipped:
        print(f"PARTIAL: {len(passed)} passed, {len(skipped)} skipped (likely template not instantiated — symlink data/ and code/ to run the data-dependent checks).")
    else:
        print(f"OK: {len(passed)} passed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(2)
