"""Pre-flight checks for a `final-model/` bundle.

Verifies file presence, manifest sanity, predict-function importability, signature
compatibility, and that a real sample segment round-trips through the predictor
with the expected return shape. Returns a structured report; never raises on a
per-check failure.

Exported function: ``preflight``.
"""

from __future__ import annotations

import importlib.util
import inspect
import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


_TRUNCATE = 300


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


def preflight(final_model_dir: str | Path) -> dict[str, Any]:
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

    # --- 10. experiments_md_has_alternatives_header -----------------------------
    # m3.v3 replaces the "Rung: 1+ required" gate with a stronger upstream gate:
    # EXPERIMENTS.md must open with an "Alternatives considered" block listing
    # >= 5 candidate model shapes BEFORE any experiment entry. See
    # references/exploration-discipline.md.
    _check_alternatives_header(bundle, checks, errors)

    # --- 11. models_md_has_three_candidates -------------------------------------
    # m3.v3 makes models first-class. MODELS.md must list >= 3 candidates in
    # models/, at least one tagged `structure: differs-from-v1`.
    _check_models_registry(bundle, checks, errors)

    # --- 12. predict_differs_structurally_from_v1 -------------------------------
    # Warn if the shipped predict() is functionally equivalent to V1 on a sample
    # segment (max abs yaw diff below tolerance). Catches "I refit V1 and shipped
    # it". The check warns rather than fails: shipping V1 is permitted when all
    # candidates lost, but it must be an explicit choice.
    if fn is not None and sig_ok:
        _check_predict_differs_from_v1(fn, manifest, checks, errors)
    else:
        _skip(checks, errors, "predict_differs_structurally_from_v1", "predict not invokable")

    passes = all(c["status"] in ("pass", "warn") for c in checks)
    return {"passes": passes, "checks": checks, "errors": errors}


def _find_experiments_md(bundle: Path) -> Path | None:
    """Locate EXPERIMENTS.md (bundle.parent / cwd / bundle)."""
    candidates = [
        bundle.parent / "EXPERIMENTS.md",
        Path("EXPERIMENTS.md"),
        bundle / "EXPERIMENTS.md",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


def _find_models_md(bundle: Path) -> Path | None:
    """Locate MODELS.md (bundle.parent / cwd / bundle)."""
    candidates = [
        bundle.parent / "MODELS.md",
        Path("MODELS.md"),
        bundle / "MODELS.md",
    ]
    for c in candidates:
        if c.exists() and c.is_file():
            return c
    return None


# --- 10. Alternatives header ------------------------------------------------

_ALTERNATIVES_HEADING_RE = re.compile(
    r"^\s*#{1,3}\s*Alternatives\s+considered\b", re.IGNORECASE | re.MULTILINE
)
_ALT_BULLET_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+\S", re.MULTILINE)
_STRUCTURE_TAG_RE = re.compile(
    r"\(\s*structure\s*\)|\bstructure:\s*differs-from-v1\b", re.IGNORECASE
)


def _check_alternatives_header(bundle: Path, checks: list[dict], errors: list[str]) -> None:
    name = "experiments_md_has_alternatives_header"
    experiments = _find_experiments_md(bundle)
    if experiments is None:
        _add(
            checks,
            errors,
            name,
            "fail",
            "EXPERIMENTS.md not found at bundle.parent/, cwd, or bundle/. "
            "Per AGENTS.md § 'Inner loop', open EXPERIMENTS.md with an "
            "'Alternatives considered' block listing >= 5 candidate model shapes.",
        )
        return
    try:
        text = experiments.read_text(encoding="utf-8")
    except OSError as e:
        _add(checks, errors, name, "fail", f"EXPERIMENTS.md exists but couldn't be read: {_truncate(repr(e))}")
        return

    m = _ALTERNATIVES_HEADING_RE.search(text)
    if not m:
        _add(
            checks,
            errors,
            name,
            "fail",
            "EXPERIMENTS.md has no '## Alternatives considered' heading. "
            "See references/exploration-discipline.md § 'Before you commit'.",
        )
        return

    # Capture body until the next heading (## or #).
    body_start = m.end()
    next_heading = re.search(r"^\s*#{1,3}\s", text[body_start:], re.MULTILINE)
    body = text[body_start : body_start + (next_heading.start() if next_heading else len(text) - body_start)]

    bullets = _ALT_BULLET_RE.findall(body)
    structurally_distinct = len(_STRUCTURE_TAG_RE.findall(body))

    if len(bullets) < 5:
        _add(
            checks,
            errors,
            name,
            "fail",
            f"'Alternatives considered' has {len(bullets)} bullet(s); need >= 5. "
            "Tag each line with `(structure)` or `structure: differs-from-v1` "
            "if it differs from V1's kinematic-single-track shape. "
            "See references/exploration-discipline.md.",
        )
        return
    if structurally_distinct < 3:
        _add(
            checks,
            errors,
            name,
            "fail",
            f"'Alternatives considered' has {structurally_distinct} entries tagged as "
            "structurally distinct from V1; need >= 3. Tag with `(structure)` or "
            "`structure: differs-from-v1`. See references/exploration-discipline.md.",
        )
        return
    _add(
        checks,
        errors,
        name,
        "pass",
        f"{experiments.name} lists {len(bullets)} alternatives, "
        f"{structurally_distinct} tagged structurally distinct from V1",
    )


# --- 11. MODELS.md registry -------------------------------------------------

_MODELS_ENTRY_RE = re.compile(r"^\s*##\s+(\S.*)$", re.MULTILINE)
_DIFFERS_FROM_V1_RE = re.compile(
    r"structure\s*:\s*differs-from-v1\b", re.IGNORECASE
)


def _check_models_registry(bundle: Path, checks: list[dict], errors: list[str]) -> None:
    name = "models_md_has_three_candidates"
    models_md = _find_models_md(bundle)
    if models_md is None:
        _add(
            checks,
            errors,
            name,
            "fail",
            "MODELS.md not found at bundle.parent/, cwd, or bundle/. "
            "m3.v3 requires a registry of >= 3 candidate models — see AGENTS.md § 'Models as first-class objects'.",
        )
        return
    try:
        text = models_md.read_text(encoding="utf-8")
    except OSError as e:
        _add(checks, errors, name, "fail", f"MODELS.md exists but couldn't be read: {_truncate(repr(e))}")
        return
    entries = _MODELS_ENTRY_RE.findall(text)
    differ_count = len(_DIFFERS_FROM_V1_RE.findall(text))
    if len(entries) < 3:
        _add(
            checks,
            errors,
            name,
            "fail",
            f"MODELS.md has {len(entries)} candidate entries (##-level headings); need >= 3. "
            "See AGENTS.md § 'Models as first-class objects'.",
        )
        return
    if differ_count < 1:
        _add(
            checks,
            errors,
            name,
            "fail",
            f"MODELS.md has {len(entries)} entries but 0 tagged `structure: differs-from-v1`. "
            "At least one candidate must attack V1 structurally, not just refit V1's coefficients.",
        )
        return
    _add(
        checks,
        errors,
        name,
        "pass",
        f"{models_md.name} registers {len(entries)} candidate(s); {differ_count} tagged differs-from-v1",
    )


# --- 12. Structural-novelty diff against V1 --------------------------------

_V1_DIFF_TOLERANCE_RAD = 1e-3  # max abs |yaw_pred - yaw_v1| below this -> warn


def _check_predict_differs_from_v1(
    fn, manifest: dict | None, checks: list[dict], errors: list[str]
) -> None:
    name = "predict_differs_structurally_from_v1"
    try:
        # Find V1 baseline. Conventionally code/v1_baseline.py — we expose it via
        # sys.path so the bundle's code/ symlink resolves it.
        v1_path = Path("code") / "v1_baseline.py"
        if not v1_path.exists():
            _add(checks, errors, name, "skip", f"V1 baseline not found at {v1_path}; skipping diff check")
            return
        sys.path.insert(0, str(Path("code").resolve()))
        try:
            from v1_baseline import predict_v1  # type: ignore
        finally:
            try:
                sys.path.remove(str(Path("code").resolve()))
            except ValueError:
                pass

        # Pick a non-Tesla platform with sample data (V1 only varies on those).
        declared = (manifest or {}).get("platform_support") or []
        sample = None
        sample_platform = None
        for p in declared:
            if p == "TESLA_MODEL_3":
                continue
            s = _sample_sim_csv(p)
            if s is not None:
                sample = s
                sample_platform = p
                break
        if sample is None:
            _add(checks, errors, name, "skip", "no non-Tesla sample sim.csv found; skipping diff check")
            return

        sim_df = pd.read_csv(sample)
        out_shipped = fn(sim_df, sample_platform)
        out_v1 = predict_v1(sim_df, sample_platform)
        diff = (
            out_shipped["yaw_rate_pred_rads"].to_numpy()
            - out_v1["yaw_rate_pred_rads"].to_numpy()
        )
        max_abs = float(np.max(np.abs(diff)))
        if max_abs < _V1_DIFF_TOLERANCE_RAD:
            _add(
                checks,
                errors,
                name,
                "warn",
                f"shipped predict differs from V1 by max |Δyaw| = {max_abs:.6f} rad/s "
                f"on {sample_platform} (< {_V1_DIFF_TOLERANCE_RAD} tolerance). "
                "This looks like V1 with re-fitted coefficients, not a structurally-different model. "
                "If your candidates all lost to V1 and you're intentionally shipping V1, document "
                "this in REPORT.md. Otherwise ship a candidate from models/.",
            )
            return
        _add(
            checks,
            errors,
            name,
            "pass",
            f"max |Δyaw| vs V1 = {max_abs:.4f} rad/s on {sample_platform} (above {_V1_DIFF_TOLERANCE_RAD} tolerance)",
        )
    except Exception as e:
        _add(checks, errors, name, "fail", _truncate(repr(e)))
