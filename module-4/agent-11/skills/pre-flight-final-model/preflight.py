"""Pre-flight checks for a `final-model/` bundle.

Verifies file presence, manifest sanity, predict-function importability, signature
compatibility, and that a real sample segment round-trips through the predictor
with the expected return shape. Returns a structured report; never raises on a
per-check failure.

m4 adds these gates on top of the m3.v2 checks:
- models_md_has_min_candidates
- tree_json_consistent
- tree_has_diverse_rungs
- rpi_artifacts_locked_if_present
- shipped_is_promote_to_leader
- (when --final) test_split_gate — reads the frozen test split and warns on
  dev/test gap > 5%

m4.v1.01 adds:
- bias_without_route_cv — hard refuse on per-platform bias terms without a
  route_cv_sigma sibling. Closes the m4.v1 agent-07 mode (cohort §6 + §9).
- parent_baseline_declared — PLAN.md must name V0/V1/fresh with evidence.
  Closes the m4.v1 agent-10 mode (built on V0).
- iterate_history_min — EXPERIMENTS.md must contain ≥ MIN_ITERATE_HISTORY
  entries written by skills/iterate (replaces the gameable file-count check).
- report_cites_rejected — REPORT.md must name ≥1 rejected candidate.

Exported function: ``preflight``.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import pandas as pd


_TRUNCATE = 300
DEV_TEST_GAP_WARN_PCT = 5.0
# m4.v1.01 — bumped from 4 in m4.v1; reduces single-candidate-ship pattern.
MIN_MODELS_MD_CANDIDATES = 6
# m4.v1.01 — minimum iterate-written EXPERIMENTS.md entries. Closes the
# m4.v1 agent-07 "touch files, ship one candidate" mode. See _shared/gates.py.
MIN_ITERATE_HISTORY = 4
V2_LAYOUT_MARKER = "phases/3-implement"


def _truncate(s: str, n: int = _TRUNCATE) -> str:
    s = str(s)
    return s if len(s) <= n else s[: n - 3] + "..."


def _add(checks: list[dict], errors: list[str], name: str, status: str, detail: str) -> None:
    checks.append({"name": name, "status": status, "detail": detail})
    if status == "fail":
        errors.append(f"{name}: {detail}")


def _skip(checks: list[dict], errors: list[str], name: str, reason: str) -> None:
    # A skip caused by an upstream failure should also count as not-passing.
    checks.append({"name": name, "status": "skip", "detail": reason})
    errors.append(f"{name}: skipped ({reason})")


def _sample_sim_csv(platform: str = "FORD_MUSTANG_MACH_E_MK1") -> Path | None:
    """Return the first sim.csv under data/sim-only/segments/<platform>, or None."""
    root = Path(f"data/sim-only/segments/{platform}")
    if not root.exists():
        return None
    matches = sorted(root.glob("**/sim.csv"))
    return matches[0] if matches else None


def _load_predict_module(predict_path: Path, bundle_dir: Path):
    """Load predict.py via importlib without polluting sys.modules across calls.

    Temporarily prepends ``bundle_dir`` to ``sys.path`` so the module can import
    siblings (helpers, coeffs loaders, etc.).
    """
    sys.path.insert(0, str(bundle_dir))
    try:
        spec = importlib.util.spec_from_file_location(
            f"_preflight_predict_{abs(hash(str(predict_path)))}",
            str(predict_path),
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"could not build import spec for {predict_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        try:
            sys.path.remove(str(bundle_dir))
        except ValueError:
            pass


def preflight(final_model_dir: str | Path, *, final: bool = False) -> dict[str, Any]:
    """Validate a `final-model/` deliverable bundle.

    Parameters
    ----------
    final_model_dir : str | Path
        Path to the directory containing the bundle (predict.py, manifest.json,
        REPORT.md, plus any helper files).

    Returns
    -------
    dict with keys:
        passes : bool — True only if every executed check passed and none skipped.
        checks : list of {name, status ("pass"|"fail"|"skip"), detail}.
        errors : list[str] — one entry per failing or skipped check.
    """
    bundle = Path(final_model_dir)
    checks: list[dict] = []
    errors: list[str] = []

    # --- 1. directory_exists ----------------------------------------------------
    if bundle.exists() and bundle.is_dir():
        _add(checks, errors, "directory_exists", "pass", f"found {bundle}")
        dir_ok = True
    else:
        _add(checks, errors, "directory_exists", "fail", f"not a directory: {bundle}")
        dir_ok = False

    # --- 2. predict_py_present --------------------------------------------------
    predict_path = bundle / "predict.py"
    if not dir_ok:
        _skip(checks, errors, "predict_py_present", "directory missing")
        predict_ok = False
    elif predict_path.exists() and predict_path.is_file():
        _add(checks, errors, "predict_py_present", "pass", str(predict_path))
        predict_ok = True
    else:
        _add(checks, errors, "predict_py_present", "fail", f"missing {predict_path}")
        predict_ok = False

    # --- 3. manifest_json_present -----------------------------------------------
    manifest_path = bundle / "manifest.json"
    if not dir_ok:
        _skip(checks, errors, "manifest_json_present", "directory missing")
        manifest_present = False
    elif manifest_path.exists() and manifest_path.is_file():
        _add(checks, errors, "manifest_json_present", "pass", str(manifest_path))
        manifest_present = True
    else:
        _add(checks, errors, "manifest_json_present", "fail", f"missing {manifest_path}")
        manifest_present = False

    # --- 4. report_md_present ---------------------------------------------------
    report_path = bundle / "REPORT.md"
    if not dir_ok:
        _skip(checks, errors, "report_md_present", "directory missing")
    elif not report_path.exists():
        _add(checks, errors, "report_md_present", "fail", f"missing {report_path}")
    else:
        try:
            size = report_path.stat().st_size
            if size >= 100:
                _add(checks, errors, "report_md_present", "pass", f"{size} bytes")
            else:
                _add(
                    checks,
                    errors,
                    "report_md_present",
                    "fail",
                    f"REPORT.md too small ({size} bytes; need >= 100)",
                )
        except OSError as e:
            _add(checks, errors, "report_md_present", "fail", _truncate(repr(e)))

    # --- 5. manifest_parses -----------------------------------------------------
    manifest: dict | None = None
    predict_callable_name = "predict"
    if not manifest_present:
        _skip(checks, errors, "manifest_parses", "manifest.json missing")
    else:
        try:
            with manifest_path.open("r", encoding="utf-8") as fh:
                manifest = json.load(fh)
            if not isinstance(manifest, dict):
                raise ValueError(f"manifest must be a JSON object, got {type(manifest).__name__}")
            ps = manifest.get("platform_support")
            if not isinstance(ps, list) or not all(isinstance(x, str) for x in ps):
                raise ValueError("manifest.platform_support must be a list of strings")
            pc = manifest.get("predict_callable")
            if not isinstance(pc, str) or ":" not in pc:
                raise ValueError(
                    "manifest.predict_callable must be a string like 'predict.py:predict'"
                )
            _, predict_callable_name = pc.split(":", 1)
            _add(
                checks,
                errors,
                "manifest_parses",
                "pass",
                f"platform_support={ps}, predict_callable={pc}",
            )
        except Exception as e:
            manifest = None
            _add(checks, errors, "manifest_parses", "fail", _truncate(repr(e)))

    # --- 6. predict_imports -----------------------------------------------------
    module = None
    if not predict_ok:
        _skip(checks, errors, "predict_imports", "predict.py missing")
    else:
        try:
            module = _load_predict_module(predict_path, bundle)
            _add(checks, errors, "predict_imports", "pass", "import OK")
        except Exception as e:
            module = None
            _add(checks, errors, "predict_imports", "fail", _truncate(repr(e)))

    # --- 7. predict_callable_exists --------------------------------------------
    fn = None
    if module is None:
        _skip(checks, errors, "predict_callable_exists", "predict.py did not import")
    else:
        try:
            fn = getattr(module, predict_callable_name, None)
            if fn is None:
                raise AttributeError(
                    f"function '{predict_callable_name}' not found on predict module"
                )
            if not callable(fn):
                raise TypeError(f"'{predict_callable_name}' is not callable")
            _add(checks, errors, "predict_callable_exists", "pass", predict_callable_name)
        except Exception as e:
            fn = None
            _add(checks, errors, "predict_callable_exists", "fail", _truncate(repr(e)))

    # --- 8. predict_signature_compatible ---------------------------------------
    sig_ok = False
    if fn is None:
        _skip(checks, errors, "predict_signature_compatible", "predict callable unavailable")
    else:
        try:
            sig = inspect.signature(fn)
            params = list(sig.parameters.values())
            has_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
            positional_kinds = (
                inspect.Parameter.POSITIONAL_ONLY,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.VAR_POSITIONAL,
            )
            positional = [p for p in params if p.kind in positional_kinds]
            # accepts >= 2 positional, or has VAR_POSITIONAL, or has **kwargs.
            accepts_two = (
                any(p.kind == inspect.Parameter.VAR_POSITIONAL for p in params)
                or len(positional) >= 2
                or has_var_kw
            )
            if not accepts_two:
                raise TypeError(
                    f"signature {sig} does not accept (sim_df, platform) positionally"
                )
            _add(checks, errors, "predict_signature_compatible", "pass", str(sig))
            sig_ok = True
        except Exception as e:
            _add(checks, errors, "predict_signature_compatible", "fail", _truncate(repr(e)))

    # --- 9. predict_returns_correct_shape (every declared platform) -------------
    # Runs the predict on one sample from EACH platform in manifest.platform_support
    # (where sample data is available). Catches platform-conditional failures —
    # e.g. a predict that works on Mach-E but raises on IONIQ.
    if fn is None or not sig_ok:
        _skip(checks, errors, "predict_returns_correct_shape", "predict not invokable")
    else:
        declared_platforms = (manifest or {}).get("platform_support") or [
            "FORD_MUSTANG_MACH_E_MK1"
        ]
        platforms_tested: list[str] = []
        platforms_skipped: list[str] = []
        platforms_failed: list[tuple[str, str]] = []
        for platform in declared_platforms:
            sample = _sample_sim_csv(platform)
            if sample is None:
                platforms_skipped.append(platform)
                continue
            try:
                sim_df = pd.read_csv(sample)
                out = fn(sim_df, platform)
                if not isinstance(out, pd.DataFrame):
                    raise TypeError(
                        f"predict must return a pandas.DataFrame, got {type(out).__name__}"
                    )
                if "yaw_rate_pred_rads" not in out.columns:
                    raise ValueError(
                        f"returned DataFrame missing 'yaw_rate_pred_rads' column; has {list(out.columns)}"
                    )
                if len(out.index) != len(sim_df.index) or not (out.index == sim_df.index).all():
                    raise ValueError("returned DataFrame index does not match input sim_df.index")
                if out["yaw_rate_pred_rads"].isna().any():
                    raise ValueError("yaw_rate_pred_rads contains NaN")
                for opt in ("x_m", "y_m"):
                    if opt in out.columns and out[opt].isna().any():
                        raise ValueError(f"{opt} contains NaN")
                platforms_tested.append(platform)
            except Exception as e:
                platforms_failed.append((platform, _truncate(repr(e))))

        if platforms_failed:
            detail = "; ".join(f"{p}: {err}" for p, err in platforms_failed)
            _add(checks, errors, "predict_returns_correct_shape", "fail", detail)
        elif not platforms_tested:
            _add(
                checks,
                errors,
                "predict_returns_correct_shape",
                "skip",
                f"no sample sim.csv found for any declared platform ({declared_platforms})",
            )
        else:
            detail = f"passed on {platforms_tested}"
            if platforms_skipped:
                detail += f"; no sample data for {platforms_skipped}"
            _add(checks, errors, "predict_returns_correct_shape", "pass", detail)

    # --- 10. experiments_md_has_rung_climb_attempt ------------------------------
    # The template defaults to "attempt a structural climb past rung 0" — see
    # AGENTS.md § "On exploration — the default is to climb". This check is the
    # enforcement: EXPERIMENTS.md (one level up from final-model/) must contain
    # at least one entry tagged `Rung: 1`, `Rung: 2`, `Rung: 3`, or
    # `Rung: orthogonal`. The shipped model can still be rung 0; the attempt
    # has to be logged.
    _check_rung_climb(bundle, checks, errors)

    # --- m4 gates ---------------------------------------------------------------
    template_root = _find_template_root(bundle)
    if template_root is None:
        # Fall back to cwd so we still emit the m4 gate rows (visibility matters).
        template_root = _find_template_root(Path.cwd())
    if template_root is None:
        _skip(checks, errors, "m4_gates", "could not locate template root (AGENTS.md + skills/)")
        # Even without a template root, emit the test_split_gate row so its
        # absence/presence isn't ambiguous to the cohort reviewer.
        _add(
            checks, errors, "test_split_gate", "skip",
            "preflight could not locate the template root; test split not checked.",
        )
        # Don't error-push this skip.
        for e in list(errors):
            if e.startswith("test_split_gate: skipped"):
                errors.remove(e)
    else:
        _check_models_md(template_root, checks, errors)
        _check_tree_consistency(template_root, checks, errors)
        _check_rung_diversity(template_root, checks, errors)
        _check_rpi_artifacts_locked(template_root, checks, errors)
        _check_shipped_is_leader(template_root, bundle, fn, checks, errors)
        # m4.v1.01 — new gates.
        _check_bias_without_route_cv(template_root, bundle, checks, errors)
        _check_parent_baseline_declared(template_root, checks, errors)
        _check_iterate_history(template_root, checks, errors)
        _check_report_cites_rejected(template_root, bundle, checks, errors)
        if final:
            _check_test_split_gate(template_root, fn, checks, errors)
        else:
            _add(
                checks, errors, "test_split_gate", "skip",
                "preflight invoked without --final; test split not read. "
                "Re-run with --final at the very end to score on the frozen test split.",
            )
            # Don't push "test_split_gate skip" into errors — it's intentional
            # for non-final runs. Pop it back out.
            for e in list(errors):
                if e.startswith("test_split_gate: skipped"):
                    errors.remove(e)

    passes = all(c["status"] == "pass" for c in checks)
    return {"passes": passes, "checks": checks, "errors": errors}


# ---------------------------------------------------------------------------
# m4 gate helpers
# ---------------------------------------------------------------------------

def _find_template_root(start: Path) -> Path | None:
    start = start.resolve()
    for ancestor in (start, *start.parents):
        if (ancestor / "AGENTS.md").exists() and (ancestor / "skills").is_dir():
            return ancestor
    return None


_MODELS_MD_ENTRY_RE = re.compile(r"^## ([^\s#].*)$", re.MULTILINE)
_MODELS_MD_RUNG_RE = re.compile(r"^- rung:\s*(\S+)", re.MULTILINE)
_MODELS_MD_GATE_RE = re.compile(r"^- gate:\s*(pass|warn|fail)\b", re.MULTILINE)


def _parse_models_md(template_root: Path) -> list[dict]:
    path = template_root / "MODELS.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    # Split on each `## ` header and parse rung + gate from each block.
    entries: list[dict] = []
    parts = re.split(r"^## ([^\s#].*)$", text, flags=re.MULTILINE)
    # parts = [preamble, name1, body1, name2, body2, ...]
    for i in range(1, len(parts), 2):
        name = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        if name.startswith("<") or name.startswith("model-name"):
            continue  # skeleton placeholder
        rung_m = _MODELS_MD_RUNG_RE.search(body)
        gate_m = _MODELS_MD_GATE_RE.search(body)
        entries.append({
            "name": name,
            "rung": rung_m.group(1) if rung_m else None,
            "gate": gate_m.group(1) if gate_m else None,
        })
    return entries


def _check_models_md(template_root: Path, checks: list[dict], errors: list[str]) -> None:
    name = "models_md_has_min_candidates"
    entries = _parse_models_md(template_root)
    n = len(entries)
    if n < MIN_MODELS_MD_CANDIDATES:
        _add(checks, errors, name, "fail",
             f"MODELS.md has {n} candidate entries; preflight requires "
             f">= {MIN_MODELS_MD_CANDIDATES}. m4.v1.01 bumped this from 4 because "
             "single-candidate ships (m4.v1 agent-07) shipped at +44.6% yaw "
             "vs the cohort median +56.2%. Build more candidates via skills/iterate/.")
        return
    # m4.v1.01: require ≥ 2 structurally-different candidates (was 1 in m4.v1).
    diverse = [e for e in entries if e["rung"] in ("1", "2", "3", "orthogonal")]
    if len(diverse) < 2:
        _add(checks, errors, name, "fail",
             f"MODELS.md has {n} entries but only {len(diverse)} tagged "
             "rung 1/2/3/orthogonal. m4.v1.01 requires ≥ 2 structurally-different "
             "candidates (m4.v1 required 1; the launch-rungs default fan-out "
             "produces 4+ for free).")
        return
    _add(checks, errors, name, "pass",
         f"{n} candidates, {len(diverse)} structurally different.")


def _check_tree_consistency(template_root: Path, checks: list[dict], errors: list[str]) -> None:
    name = "tree_json_consistent"
    tree_path = template_root / "TREE.json"
    if not tree_path.exists():
        _add(checks, errors, name, "fail", "TREE.json not found; iterate skill has never run.")
        return
    try:
        tree = json.loads(tree_path.read_text())
    except Exception as e:
        _add(checks, errors, name, "fail", f"TREE.json unparseable: {_truncate(repr(e))}")
        return
    tree_names = {n.get("name") for n in tree.get("nodes", [])}
    md_names = {e["name"] for e in _parse_models_md(template_root)}
    only_tree = tree_names - md_names
    only_md = md_names - tree_names
    if only_tree or only_md:
        _add(checks, errors, name, "fail",
             f"TREE.json / MODELS.md drift: only-in-tree={sorted(only_tree)}, "
             f"only-in-md={sorted(only_md)}. Edits to MODELS.md should only "
             "happen via skills/iterate/.")
        return
    _add(checks, errors, name, "pass",
         f"{len(tree_names)} nodes consistent across TREE.json and MODELS.md.")


def _check_rung_diversity(template_root: Path, checks: list[dict], errors: list[str]) -> None:
    name = "tree_has_diverse_rungs"
    tree_path = template_root / "TREE.json"
    if not tree_path.exists():
        _skip(checks, errors, name, "TREE.json missing")
        return
    try:
        tree = json.loads(tree_path.read_text())
    except Exception:
        _skip(checks, errors, name, "TREE.json unparseable")
        return
    rungs = {str(n.get("rung")) for n in tree.get("nodes", [])}
    rungs.discard(None)
    rungs.discard("None")
    if len(rungs) < 2:
        _add(checks, errors, name, "fail",
             f"TREE.json shows {len(rungs)} distinct rung value(s): {sorted(rungs)}. "
             "All-rung-0 search = the m3.v2 cohort collapse pattern. Build a "
             "structurally-different candidate (orthogonal or rung 1+).")
        return
    _add(checks, errors, name, "pass", f"distinct rungs in search: {sorted(rungs)}")


def _check_rpi_artifacts_locked(template_root: Path, checks: list[dict], errors: list[str]) -> None:
    name = "rpi_artifacts_locked_if_present"
    # v1 path
    v1_research = template_root / "rpi" / "artifacts" / "RESEARCH.md"
    v1_plan = template_root / "rpi" / "artifacts" / "PLAN.md"
    # v2 path
    v2_research = template_root / "phases" / "1-research" / "artifacts" / "RESEARCH.md"
    v2_plan = template_root / "phases" / "2-plan" / "artifacts" / "PLAN.md"

    targets = [p for p in (v1_research, v1_plan, v2_research, v2_plan) if p.exists()]
    if not targets:
        _add(checks, errors, name, "pass", "no RPI artifacts present (RPI not used)")
        return
    unlocked = [str(p) for p in targets if os.access(p, os.W_OK)]
    if unlocked:
        _add(checks, errors, name, "fail",
             f"RPI artifacts present but writable: {unlocked}. "
             "Run `bash lock.sh <path>` on each. Preflight refuses to ship if "
             "any phase artifact could still be edited.")
        return
    _add(checks, errors, name, "pass",
         f"{len(targets)} RPI artifact(s) locked (chmod -w).")


def _check_shipped_is_leader(template_root: Path, bundle: Path, fn, checks: list[dict], errors: list[str]) -> None:
    """The shipped predict.py must correspond to a TREE.json node whose verdict
    is promote_to_leader (or shipped). This is what closes the stagnation
    soft-refusal chain — a stagnant-branch node has its verdict capped at
    `keep` in iterate, so it cannot satisfy this check."""
    name = "shipped_is_promote_to_leader"
    tree_path = template_root / "TREE.json"
    if not tree_path.exists():
        _add(checks, errors, name, "fail",
             "TREE.json not found. Shipped models must have been scored through "
             "skills/iterate/ and reached verdict=promote_to_leader.")
        return
    try:
        tree = json.loads(tree_path.read_text())
    except Exception:
        _skip(checks, errors, name, "TREE.json unparseable")
        return
    promoted = [n for n in tree.get("nodes", []) if n.get("verdict") in ("promote_to_leader", "shipped")]
    if not promoted:
        _add(checks, errors, name, "fail",
             "No TREE.json node has verdict=promote_to_leader. Every iterate "
             "call returned 'keep' or 'shelve' — typically the stagnation "
             "soft-refusal cap, an unresolved gate warn, or a residual still "
             "showing structure. Address the cause and re-iterate.")
        return
    # Heuristic best-effort identity: match the shipped predict.py's name to a
    # promoted node. We don't behavioural-hash; that's the extension hook.
    shipped_predict = bundle / "predict.py"
    if not shipped_predict.exists():
        _skip(checks, errors, name, "final-model/predict.py missing")
        return
    text = shipped_predict.read_text(encoding="utf-8", errors="ignore")
    # Look for a likely re-export comment or import from one of the promoted node dirs.
    hits = [p["name"] for p in promoted if p["name"] in text or p.get("dir_rel", "") in text]
    if not hits:
        _add(checks, errors, name, "warn",
             f"{len(promoted)} promoted node(s) in TREE.json but the shipped "
             f"predict.py doesn't reference any by name. If you ship a "
             "re-export, name the source candidate in a comment so this check "
             "can verify it. Promoted: " + ", ".join(p["name"] for p in promoted))
        # warn, not fail — we don't want to block a legitimate inline-copied ship,
        # but we want the cohort reviewer to confirm.
        return
    _add(checks, errors, name, "pass",
         f"shipped predict.py references promoted candidate(s): {hits}")


def _check_test_split_gate(template_root: Path, fn, checks: list[dict], errors: list[str]) -> None:
    """When invoked with --final, score the shipped predict on the frozen test
    split and warn on dev/test gap > 5%."""
    name = "test_split_gate"
    if fn is None:
        _skip(checks, errors, name, "predict callable unavailable")
        return
    test_root = template_root / "data" / "sim" / "test"
    if not test_root.exists():
        _add(checks, errors, name, "warn",
             f"data/sim/test/ not present at {test_root}. The frozen test split "
             "isn't seeded in this environment — dev/test gap not measurable.")
        return
    test_paths = sorted(test_root.rglob("sim.csv"))
    if not test_paths:
        _add(checks, errors, name, "warn", "test split exists but contains no sim.csv files.")
        return
    # Ensure the score module is reachable.
    sys.path.insert(0, str(template_root))
    try:
        from skills.score_model.score import score  # type: ignore
    except ImportError as e:
        _skip(checks, errors, name, f"could not import score-model: {_truncate(repr(e))}")
        return
    try:
        # final=True is the ONLY way the test-split refusal in score() relents.
        test_result = score(fn, segment_paths=test_paths, final=True)
        dev_paths = sorted((template_root / "data" / "sim" / "segments").rglob("sim.csv"))
        dev_result = score(fn, segment_paths=dev_paths)
    except Exception as e:
        _add(checks, errors, name, "fail",
             f"scoring on test split raised: {_truncate(repr(e))}")
        return
    dev_yaw = dev_result["yaw_rate_rmse"]
    test_yaw = test_result["yaw_rate_rmse"]
    dev_cte = dev_result["cte_rmse"]
    test_cte = test_result["cte_rmse"]
    yaw_gap_pct = 100.0 * abs(dev_yaw - test_yaw) / max(dev_yaw, 1e-9)
    cte_gap_pct = 100.0 * abs(dev_cte - test_cte) / max(dev_cte, 1e-9)
    detail = (
        f"dev yaw={dev_yaw:.6f} test yaw={test_yaw:.6f} (gap {yaw_gap_pct:.1f}%); "
        f"dev cte={dev_cte:.3f} test cte={test_cte:.3f} (gap {cte_gap_pct:.1f}%)"
    )
    if yaw_gap_pct > DEV_TEST_GAP_WARN_PCT or cte_gap_pct > DEV_TEST_GAP_WARN_PCT:
        _add(checks, errors, name, "warn",
             f"dev/test gap exceeds {DEV_TEST_GAP_WARN_PCT}% threshold — possible "
             f"overfit to dev under the closed-loop iteration count. {detail}")
        return
    _add(checks, errors, name, "pass", detail)


_RUNG_CLIMB_RE = re.compile(
    r"^\s*[-*]?\s*Rung\s*:\s*(1|2|3|orthogonal)\b",
    re.IGNORECASE | re.MULTILINE,
)


def _find_experiments_md(bundle: Path) -> Path | None:
    """Locate EXPERIMENTS.md. Conventionally one level up from final-model/, but
    we also check the cwd and bundle itself as fallbacks."""
    candidates = [
        bundle.parent / "EXPERIMENTS.md",
        Path("EXPERIMENTS.md"),
        bundle / "EXPERIMENTS.md",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def _check_rung_climb(bundle: Path, checks: list[dict], errors: list[str]) -> None:
    name = "experiments_md_has_rung_climb_attempt"
    experiments = _find_experiments_md(bundle)
    if experiments is None:
        _add(
            checks,
            errors,
            name,
            "fail",
            "EXPERIMENTS.md not found at bundle.parent/, cwd, or bundle/. "
            "Per AGENTS.md § 'On exploration', log at least one Rung: 1+ or Rung: orthogonal attempt.",
        )
        return
    try:
        text = experiments.read_text(encoding="utf-8")
    except OSError as e:
        _add(checks, errors, name, "fail", f"EXPERIMENTS.md exists but couldn't be read: {_truncate(repr(e))}")
        return
    matches = _RUNG_CLIMB_RE.findall(text)
    if not matches:
        _add(
            checks,
            errors,
            name,
            "fail",
            f"EXPERIMENTS.md ({experiments}) has no entry tagged `Rung: 1`, `Rung: 2`, `Rung: 3`, "
            "or `Rung: orthogonal`. The template defaults to a structural climb attempt — see "
            "AGENTS.md § 'On exploration' and references/dynamics-formulations.md § 'Rung 1' "
            "(Minimum viable recipe).",
        )
        return
    rungs_seen = sorted({m.lower() for m in matches})
    _add(
        checks,
        errors,
        name,
        "pass",
        f"{experiments.name} logs {len(matches)} climb attempt(s) across rung(s) {rungs_seen}",
    )


# ---------------------------------------------------------------------------
# m4.v1.01 gates — load from _shared/gates.py so iterate + preflight share logic
# ---------------------------------------------------------------------------

def _load_gates_module(template_root: Path):
    gates_path = template_root / "_shared" / "gates.py"
    if not gates_path.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("_m4v101_gates", str(gates_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


def _check_bias_without_route_cv(
    template_root: Path, bundle: Path, checks: list[dict], errors: list[str]
) -> None:
    name = "bias_without_route_cv"
    gates = _load_gates_module(template_root)
    if gates is None:
        _skip(checks, errors, name, "_shared/gates.py not loadable")
        # Don't push skip into errors — environment problem, not a model problem.
        for e in list(errors):
            if e.startswith(f"{name}: skipped"):
                errors.remove(e)
        return
    coeffs_path = bundle / "coeffs.json"
    ok, detail = gates.check_bias_without_route_cv(coeffs_path)
    _add(checks, errors, name, "pass" if ok else "fail", detail)


def _find_plan_md(template_root: Path) -> Path | None:
    """Locate PLAN.md across v1 and v2 layouts."""
    candidates = [
        template_root / "rpi" / "artifacts" / "PLAN.md",
        template_root / "phases" / "2-plan" / "artifacts" / "PLAN.md",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _check_parent_baseline_declared(
    template_root: Path, checks: list[dict], errors: list[str]
) -> None:
    name = "parent_baseline_declared"
    gates = _load_gates_module(template_root)
    if gates is None:
        _skip(checks, errors, name, "_shared/gates.py not loadable")
        for e in list(errors):
            if e.startswith(f"{name}: skipped"):
                errors.remove(e)
        return
    plan_path = _find_plan_md(template_root)
    if plan_path is None:
        # No PLAN.md — only required when RPI is in use. Vacuous pass; the
        # rpi_artifacts_locked_if_present check handles the "RPI was used"
        # case, and this gate doesn't apply otherwise.
        _add(checks, errors, name, "pass",
             "PLAN.md absent (RPI not used) — parent_baseline check vacuous.")
        return
    ok, detail = gates.check_parent_baseline_declared(plan_path)
    _add(checks, errors, name, "pass" if ok else "fail", detail)


def _check_iterate_history(
    template_root: Path, checks: list[dict], errors: list[str]
) -> None:
    name = "iterate_history_min"
    gates = _load_gates_module(template_root)
    if gates is None:
        _skip(checks, errors, name, "_shared/gates.py not loadable")
        for e in list(errors):
            if e.startswith(f"{name}: skipped"):
                errors.remove(e)
        return
    experiments_md = template_root / "EXPERIMENTS.md"
    ok, detail, _count = gates.check_iterate_history_min(
        experiments_md, min_calls=MIN_ITERATE_HISTORY
    )
    _add(checks, errors, name, "pass" if ok else "fail", detail)


def _check_report_cites_rejected(
    template_root: Path, bundle: Path, checks: list[dict], errors: list[str]
) -> None:
    name = "report_cites_rejected"
    gates = _load_gates_module(template_root)
    if gates is None:
        _skip(checks, errors, name, "_shared/gates.py not loadable")
        for e in list(errors):
            if e.startswith(f"{name}: skipped"):
                errors.remove(e)
        return
    report_md = bundle / "REPORT.md"
    ok, detail = gates.check_report_cites_rejected(report_md)
    _add(checks, errors, name, "pass" if ok else "fail", detail)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(
        description="Pre-flight check for a final-model/ bundle. Use --final at "
                    "the very end of a run to also score the frozen test split."
    )
    p.add_argument("bundle", nargs="?", default="final-model", help="path to final-model/ bundle")
    p.add_argument("--final", action="store_true",
                   help="Score on the frozen test split and warn on dev/test gap > 5%%. "
                        "Pass this exactly once, at the very end. Without it, the test "
                        "split is denied (TestSplitDeniedError at the data-access layer).")
    args = p.parse_args()
    result = preflight(args.bundle, final=args.final)
    print(json.dumps(result, indent=2, default=str))
    raise SystemExit(0 if result["passes"] else 1)
