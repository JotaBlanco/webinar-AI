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

    # --- 10. experiments_md_has_rung_climb_attempt ------------------------------
    # The template defaults to "attempt a structural climb past rung 0" — see
    # AGENTS.md § "On exploration — the default is to climb". This check is the
    # enforcement: EXPERIMENTS.md (one level up from final-model/) must contain
    # at least one entry tagged `Rung: 1`, `Rung: 2`, `Rung: 3`, or
    # `Rung: orthogonal`. The shipped model can still be rung 0; the attempt
    # has to be logged.
    _check_rung_climb(bundle, checks, errors)

    passes = all(c["status"] == "pass" for c in checks)
    return {"passes": passes, "checks": checks, "errors": errors}


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
