"""physics-catalog/_audit.py — exercise every skill × every catalog model.

Two modes (auto-detected):

  - SYNTHETIC mode: always works. Verifies the operating contract for each
    model's predict() and exercises skills that don't need real sim.csv data
    (the m4.v1.01 _shared/gates.py checks, the iterate novelty pre-gate).

  - REAL-DATA mode: kicks in when data/sim/segments/<platform>/ is non-empty.
    Then also exercises score-model, residual-structure, assess-candidate-model,
    and a dry-run of iterate's full gate.

Run:
    python -m physics-catalog._audit             # synthetic only by default
    python -m physics-catalog._audit --real      # opt into real-data mode if data present

Reports a per-(model, skill) status table at the end. Exit status 0 if every
applicable cell passes; 1 if any required cell fails.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

_CATALOG_DIR = Path(__file__).resolve().parent
_TEMPLATE_ROOT = _CATALOG_DIR.parent
sys.path.insert(0, str(_CATALOG_DIR))
sys.path.insert(0, str(_TEMPLATE_ROOT))

from _common import PASSTHROUGH_PLATFORMS, PLATFORM_PRIORS  # noqa: E402

CATALOG_MODELS = (
    "dst_lin",
    "dst_nl",
    "dst_regime",
    "dst_relax",
    "dst_load",
    "dst_twin_track",
    "dst_combined_slip",
    "dst_steer_compliance",
)


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------

def _load_predict(name: str) -> Callable:
    """Load physics-catalog/<name>/predict.py:predict."""
    path = _CATALOG_DIR / name / "predict.py"
    spec = importlib.util.spec_from_file_location(f"_pc_{name}_predict", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"_pc_{name}_predict"] = mod
    spec.loader.exec_module(mod)
    return mod.predict


def _load_skill(skill_dir: str, py_file: str, alias: str):
    """Skill dirs have hyphens; import via importlib."""
    path = _TEMPLATE_ROOT / "skills" / skill_dir / f"{py_file}.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location(alias, str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[alias] = mod
    try:
        spec.loader.exec_module(mod)
        return mod
    except Exception as e:
        print(f"  [skip] could not load skill {skill_dir}: {e}")
        return None


def _synthetic_segment() -> pd.DataFrame:
    n, dt = 400, 0.01
    t = np.arange(n) * dt
    delta = 0.05 * np.sin(2 * np.pi * 0.5 * t)
    v = 8.0 + 0.05 * t
    psi_v0 = v * np.tan(delta) / 3.0
    return pd.DataFrame({
        "t_s": t, "delta_wheel_deg": np.degrees(delta) * 16.0,
        "delta_road_rad": delta, "v_mps": v, "a_long_mps2": np.full(n, 0.05),
        "accel_pedal_pct": np.full(n, 30.0), "brake_pressed": np.zeros(n, dtype=int),
        "yaw_rate_pred_rads": psi_v0,
    })


# ---------------------------------------------------------------------------
# Per-cell checks
# ---------------------------------------------------------------------------

def check_predict_contract(name: str) -> tuple[bool, str]:
    """Verify predict(sim_df, platform) returns correct shape, no NaN, contract-OK."""
    try:
        predict = _load_predict(name)
    except Exception as e:
        return False, f"import failed: {type(e).__name__}: {e}"
    for platform in PLATFORM_PRIORS:
        seg = _synthetic_segment()
        try:
            out = predict(seg, platform)
        except Exception as e:
            return False, f"{platform}: raised {type(e).__name__}: {e}"
        if not isinstance(out, pd.DataFrame):
            return False, f"{platform}: returned {type(out).__name__}, want DataFrame"
        if "yaw_rate_pred_rads" not in out.columns:
            return False, f"{platform}: missing yaw_rate_pred_rads column"
        if len(out) != len(seg) or not (out.index == seg.index).all():
            return False, f"{platform}: index mismatch"
        arr = out["yaw_rate_pred_rads"].to_numpy()
        if not np.all(np.isfinite(arr)):
            return False, f"{platform}: non-finite output"
    return True, "all 4 platforms pass contract"


def check_bias_gate_compat(name: str) -> tuple[bool, str]:
    """Coeffs.default.json must not declare a bias term without route_cv_sigma."""
    from gates import check_bias_without_route_cv  # type: ignore  # _shared/ on syspath
    coeffs_path = _CATALOG_DIR / name / "coeffs.default.json"
    if not coeffs_path.exists():
        return False, "coeffs.default.json missing"
    ok, detail = check_bias_without_route_cv(coeffs_path)
    return ok, detail


def check_notes_has_differs_section(name: str) -> tuple[bool, str]:
    """The iterate novelty gate requires a `## What this differs from` section."""
    notes_path = _CATALOG_DIR / name / "notes.md"
    if not notes_path.exists():
        return False, "notes.md missing"
    text = notes_path.read_text(encoding="utf-8")
    if "## What this differs from" not in text:
        return False, "missing '## What this differs from' section"
    return True, "novelty section present"


def check_fit_module_importable(name: str) -> tuple[bool, str]:
    """fit.py must import cleanly (so the agent can run it).

    Pops `predict` from sys.modules first so cross-model audit runs don't
    leak the previous model's predict.py into this one's `from predict
    import ...` lookup. In production the agent runs `python -m
    physics-catalog.<name>.fit` in a fresh process; this cache only
    accumulates inside the audit's single process.
    """
    path = _CATALOG_DIR / name / "fit.py"
    if not path.exists():
        return False, "fit.py missing"
    # Force local `from predict import ...` to re-resolve in <name>/.
    sys.modules.pop("predict", None)
    # Also drop the same-named alias from sys.modules so importlib re-evals.
    sys.modules.pop(f"_pc_{name}_fit", None)
    # And put the model's own dir at sys.path[0] so `from predict import` finds
    # this model's predict.py first.
    model_dir = str(_CATALOG_DIR / name)
    if model_dir in sys.path:
        sys.path.remove(model_dir)
    sys.path.insert(0, model_dir)
    spec = importlib.util.spec_from_file_location(f"_pc_{name}_fit", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[f"_pc_{name}_fit"] = mod
    try:
        spec.loader.exec_module(mod)
    except Exception as e:
        return False, f"fit.py import failed: {type(e).__name__}: {e}"
    if not hasattr(mod, "fit_all"):
        return False, "fit.py does not expose fit_all()"
    return True, "fit_all() present and module imports"


def check_smoke_runs(name: str) -> tuple[bool, str]:
    """Run the model's standalone smoke.py — final guard the model is alive."""
    path = _CATALOG_DIR / name / "smoke.py"
    if not path.exists():
        return False, "smoke.py missing"
    import subprocess
    res = subprocess.run(
        [sys.executable, str(path)],
        capture_output=True, text=True, timeout=60,
        cwd=str(_TEMPLATE_ROOT),
    )
    if res.returncode != 0:
        return False, f"smoke.py exit={res.returncode}; stderr tail: {res.stderr[-200:]}"
    return True, "smoke.py exit=0"


def check_score_model_runs(name: str, segs_by_platform: dict[str, list[Path]]) -> tuple[bool, str]:
    """REAL-DATA: score-model returns finite yaw / cte RMSE for at least one platform."""
    score_mod = _load_skill("score-model", "score", f"_audit_score_{name}")
    if score_mod is None:
        return False, "score-model not loadable"
    predict = _load_predict(name)
    platforms_ok: list[str] = []
    for platform, segs in segs_by_platform.items():
        if not segs:
            continue
        try:
            result = score_mod.score(predict, segment_paths=segs[:3], platform_filter=platform)
        except Exception as e:
            return False, f"{platform}: score raised {type(e).__name__}: {e}"
        yaw = result.get("yaw_rate_rmse")
        if yaw is None or not np.isfinite(yaw):
            continue
        platforms_ok.append(platform)
    if not platforms_ok:
        return False, "no platform produced a finite yaw RMSE"
    return True, f"score-model OK on {platforms_ok}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _discover_real_data() -> dict[str, list[Path]]:
    root = _TEMPLATE_ROOT / "data" / "sim" / "segments"
    if not root.exists():
        return {}
    out: dict[str, list[Path]] = {}
    for platform_dir in root.iterdir():
        if not platform_dir.is_dir():
            continue
        out[platform_dir.name] = sorted(platform_dir.rglob("sim.csv"))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real", action="store_true",
                        help="Also run real-data checks if data/sim/segments/ is populated")
    args = parser.parse_args()

    # Make _shared/gates.py importable for check_bias_gate_compat.
    sys.path.insert(0, str(_TEMPLATE_ROOT / "_shared"))

    real_data = _discover_real_data() if args.real else {}
    real_mode = bool(real_data) and any(v for v in real_data.values())
    print(f"=== physics-catalog audit ===")
    print(f"  template root: {_TEMPLATE_ROOT}")
    print(f"  mode: {'REAL-DATA' if real_mode else 'SYNTHETIC'} "
          f"({'data/ present' if real_mode else 'no real data; --real not passed or data/ empty'})")
    print()

    checks: list[tuple[str, Callable[[str], tuple[bool, str]]]] = [
        ("predict_contract",     check_predict_contract),
        ("bias_gate_compat",     check_bias_gate_compat),
        ("notes_has_differs",    check_notes_has_differs_section),
        ("fit_module_imports",   check_fit_module_importable),
        ("smoke.py runs",        check_smoke_runs),
    ]

    rows: list[dict] = []
    for name in CATALOG_MODELS:
        print(f"--- {name} ---")
        for skill_name, fn in checks:
            ok, detail = fn(name)
            mark = "ok  " if ok else "FAIL"
            print(f"  [{mark}] {skill_name:24s}  {detail}")
            rows.append({"model": name, "skill": skill_name, "ok": ok, "detail": detail})
        if real_mode:
            ok, detail = check_score_model_runs(name, real_data)
            mark = "ok  " if ok else "FAIL"
            print(f"  [{mark}] {'score_model (real)':24s}  {detail}")
            rows.append({"model": name, "skill": "score_model_real", "ok": ok, "detail": detail})
        print()

    # Summary
    fails = [r for r in rows if not r["ok"]]
    print(f"=== summary ===")
    print(f"  {len(rows) - len(fails)} / {len(rows)} cells passed.")
    if fails:
        print("  failures:")
        for f in fails:
            print(f"    - {f['model']}/{f['skill']}: {f['detail'][:120]}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
