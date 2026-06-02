"""One-shot tree-search iteration step. Model-shape-agnostic.

Runs the verifier gate against a candidate model bundle and logs the result
across TREE.json, MODELS.md, EXPERIMENTS.md. See SKILL.md for the contract.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

CV_K = 5
NOISE_MULTIPLIER = 1.0  # signal must beat parent by > NOISE_MULTIPLIER * pooled CV std
STAGNATION_BRANCH_LEN = 3
DEV_TRAIN_GAP_WARN = 0.30
DIFFERS_FROM_HEADER = "## What this differs from"
IDEMPOTENCE_SMOKE_SEGMENTS = 3
V2_LAYOUT_MARKER = "phases/3-implement"


class NotesMissingDiffersFromError(RuntimeError):
    """notes.md must declare what this candidate differs from prior attempts."""


class NonIdempotentPredictError(RuntimeError):
    """predict() returned different outputs on two consecutive identical calls."""


@dataclass
class GateResult:
    status: str  # "pass" | "warn" | "fail"
    reasons: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Template-root + layout resolution (single source of truth)
# ---------------------------------------------------------------------------

def _find_template_root(start: Path) -> Path | None:
    """Walk up from `start` until we hit a directory with AGENTS.md + skills/."""
    start = start.resolve()
    for ancestor in (start, *start.parents):
        if (ancestor / "AGENTS.md").exists() and (ancestor / "skills").is_dir():
            return ancestor
    return None


def _template_root() -> Path:
    """Resolve the template root from cwd, falling back to this file's parents."""
    root = _find_template_root(Path.cwd())
    if root is not None:
        return root
    # Fallback: this file is .../skills/iterate/iterate.py
    return Path(__file__).resolve().parents[2]


def _ensure_root_on_syspath(template_root: Path) -> None:
    p = str(template_root)
    if p not in sys.path:
        sys.path.insert(0, p)


def _load_skill_module(template_root: Path, skill_dir: str, py_file: str, alias: str):
    """Load a module from `skills/<skill_dir>/<py_file>.py` via file path.

    Skill directories use hyphens (`score-model/`, `pre-flight-final-model/`),
    so `from skills.score_model.score import score` doesn't work — hyphens
    are not valid Python identifiers. Cross-skill calls go through this
    helper which loads the file directly via importlib and caches in
    sys.modules under `alias`.
    """
    if alias in sys.modules:
        return sys.modules[alias]
    path = template_root / "skills" / skill_dir / f"{py_file}.py"
    if not path.exists():
        raise ImportError(f"cannot find {path}")
    # Make the skill dir importable for any sibling-relative imports in py_file.
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


def _resolve_model_dir(model_dir: str | Path) -> Path:
    """Resolve `model_dir` against the v1/v2 layout, with a footgun guard.

    v1 layout: <root>/models/<name>/
    v2 layout: <root>/phases/3-implement/models/<name>/
    """
    p = Path(model_dir)
    if p.is_absolute() and p.exists():
        return p.resolve()
    template_root = _find_template_root(Path.cwd())
    if template_root is None:
        return p.resolve()
    is_v2 = (template_root / V2_LAYOUT_MARKER).is_dir()
    if not is_v2:
        return (template_root / p).resolve() if not p.is_absolute() else p
    # v2 layout: accept v2-prefixed or bare models/<name>/.
    if V2_LAYOUT_MARKER in str(p):
        return (template_root / p).resolve() if not p.is_absolute() else p
    if p.parts and p.parts[0] == "models":
        prefixed = template_root / V2_LAYOUT_MARKER / p
        print(f"[iterate] v2 layout detected; auto-prefixing model_dir → {prefixed}", flush=True)
        return prefixed.resolve()
    raise ValueError(
        f"iterate: model_dir {model_dir!r} does not look like models/<name>/ "
        f"or phases/3-implement/models/<name>/. Pass an explicit path under "
        f"phases/3-implement/models/."
    )


def _models_root(template_root: Path) -> Path:
    """Where candidate models live in this layout (v1 root, v2 phases/3-implement/)."""
    if (template_root / V2_LAYOUT_MARKER).is_dir():
        return template_root / V2_LAYOUT_MARKER / "models"
    return template_root / "models"


def _relative_dir(template_root: Path, model_dir: Path) -> str:
    """Path relative to template root, for use in MODELS.md entries."""
    try:
        return str(model_dir.relative_to(template_root))
    except ValueError:
        return str(model_dir)


# ---------------------------------------------------------------------------
# Bundle helpers
# ---------------------------------------------------------------------------

def _load_predict(model_dir: Path):
    pred_path = model_dir / "predict.py"
    spec = importlib.util.spec_from_file_location(f"_model_{model_dir.name}", pred_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.predict


def _load_notes(model_dir: Path) -> dict:
    notes = model_dir / "notes.md"
    out = {"rung": "0", "parent": "v1", "expected_residual": ""}
    if not notes.exists():
        return out
    for line in notes.read_text().splitlines():
        for k in ("rung", "parent", "expected_residual"):
            tag = f"- {k}:"
            if line.startswith(tag):
                out[k] = line[len(tag):].strip()
    return out


def _require_differs_section(model_dir: Path) -> None:
    """Mechanical novelty gate — see SKILL.md § 'Novelty gate'."""
    notes = model_dir / "notes.md"
    if not notes.exists():
        raise NotesMissingDiffersFromError(
            f"{notes} does not exist. notes.md is required and must include "
            f"'{DIFFERS_FROM_HEADER}' listing prior candidates and what's different."
        )
    if DIFFERS_FROM_HEADER not in notes.read_text():
        raise NotesMissingDiffersFromError(
            f"{notes} is missing the '{DIFFERS_FROM_HEADER}' section. "
            "List each prior candidate by name with a one-line claim about how this "
            "differs structurally. Iterate refuses to log otherwise."
        )


def _run_assess(model_dir: Path, template_root: Path) -> str:
    """Call assess-candidate-model to (re)populate assessment.md. Returns the
    residual_verdict line.

    Returns 'unknown' (not 'noise_floor') when assessment.md is absent — lets
    the router distinguish 'no diagnosis yet' from 'diagnosis says stop'.
    """
    try:
        assess_mod = _load_skill_module(
            template_root, "assess-candidate-model", "assess", "_iterate_assess"
        )
        assess_mod.assess(str(model_dir))
    except ImportError:
        pass
    except Exception as e:
        print(f"[iterate] assess-candidate-model raised: {e}", flush=True)

    assessment = model_dir / "assessment.md"
    if not assessment.exists():
        return "unknown"
    for line in assessment.read_text().splitlines():
        if line.lower().startswith("- residual_verdict:"):
            return line.split(":", 1)[1].strip()
    return "unknown"


def _idempotence_smoke(predict_fn, segment_paths, template_root: Path | None = None) -> None:
    """Two identical calls must produce bit-identical output."""
    import numpy as np
    import pandas as pd

    score_mod = None
    if template_root is not None:
        try:
            score_mod = _load_skill_module(template_root, "score-model", "score", "_iterate_score")
        except ImportError:
            return  # best-effort

    for p in list(segment_paths)[:IDEMPOTENCE_SMOKE_SEGMENTS]:
        # Use score's segment loader if available; otherwise fall back to a
        # minimal pandas read (predict on the input as-is).
        try:
            if score_mod is not None and hasattr(score_mod, "_load_segment_df"):
                sim_df, platform = score_mod._load_segment_df(p)
            else:
                sim_df = pd.read_csv(p)
                # platform = third-from-last path part (PLATFORM/DEVICE/ROUTE/IDX/sim.csv)
                platform = p.parents[2].name
        except Exception:
            return
        out1 = predict_fn(sim_df.copy(), platform)
        out2 = predict_fn(sim_df.copy(), platform)
        if isinstance(out1, pd.DataFrame) and isinstance(out2, pd.DataFrame):
            a1 = out1["yaw_rate_pred_rads"].to_numpy()
            a2 = out2["yaw_rate_pred_rads"].to_numpy()
            if not np.array_equal(a1, a2) and np.max(np.abs(a1 - a2)) > 1e-12:
                raise NonIdempotentPredictError(
                    f"predict() is non-deterministic on {p}: "
                    f"max abs diff = {np.max(np.abs(a1 - a2)):.3e}. "
                    "Seed RNGs, remove module-level state, or cache external lookups."
                )


# ---------------------------------------------------------------------------
# Real CV scoring — wires through score_cv from cv.py
# ---------------------------------------------------------------------------

def _cv_score(predict_fn, template_root: Path, k: int = CV_K) -> dict:
    """Score the candidate with k-fold route-grouped CV. Returns mean ± std.

    Wires score_cv from cv.py — this is the load-bearing computation. If
    score_cv is unavailable (e.g. a stripped-down env), falls back to
    single-fold score() with std=0.0 and prints a loud warning.
    """
    try:
        cv_mod = _load_skill_module(template_root, "score-model", "cv", "_iterate_cv")
        return cv_mod.score_cv(predict_fn, k=k)
    except ImportError:
        print(
            "[iterate] WARNING: score_cv unavailable; falling back to single-fold "
            "score(). CV bars will be 0.0 and signal-above-noise checks become "
            "vacuous. Fix your skills/score-model/cv.py.",
            flush=True,
        )
        score_mod = _load_skill_module(template_root, "score-model", "score", "_iterate_score")
        result = score_mod.score(predict_fn)
        return {
            "pooled": {
                "yaw_rmse": result["yaw_rate_rmse"],
                "yaw_std": 0.0,
                "cte_rmse": result["cte_rmse"],
                "cte_std": 0.0,
            },
            "per_platform": result["per_platform"],
            "folds": [],
        }


# ---------------------------------------------------------------------------
# Diff + gate + routing
# ---------------------------------------------------------------------------

def _diff(candidate: dict, baseline: dict) -> dict:
    """Compute % delta + signal-above-noise verdict against the CV σ band.

    signal_above_noise = abs(yaw_delta) > NOISE_MULTIPLIER * (cand_σ + baseline_σ)
    measured in the same units as the deltas (% of baseline yaw RMSE).
    """
    cand = candidate["pooled"]
    base = baseline["pooled"]
    yaw_pct = 100.0 * (cand["yaw_rmse"] - base["yaw_rmse"]) / max(base["yaw_rmse"], 1e-9)
    cte_pct = 100.0 * (cand["cte_rmse"] - base["cte_rmse"]) / max(base["cte_rmse"], 1e-9)
    # σ-band in same %-of-baseline units.
    combined_yaw_std = cand.get("yaw_std", 0.0) + base.get("yaw_std", 0.0)
    noise_pct = 100.0 * NOISE_MULTIPLIER * combined_yaw_std / max(base["yaw_rmse"], 1e-9)
    return {
        "yaw_delta_pct": yaw_pct,
        "cte_delta_pct": cte_pct,
        "noise_band_pct": noise_pct,
        "signal_above_noise": abs(yaw_pct) > noise_pct,
    }


def _run_gate(cand_cv: dict, vs_parent: dict, fit_diagnostics: dict | None) -> GateResult:
    reasons: list[str] = []
    if fit_diagnostics:
        for k in ("co_collapse", "stuck_on_bound", "non_convergence"):
            if fit_diagnostics.get(k):
                reasons.append(f"fit_{k}")
        gap = fit_diagnostics.get("dev_train_gap")
        if gap is not None and gap > DEV_TRAIN_GAP_WARN:
            reasons.append(f"dev_train_gap={gap:.0%}")
    if not vs_parent["signal_above_noise"] and vs_parent["yaw_delta_pct"] < 0:
        reasons.append("signal-below-noise")
    status = "fail" if any(r.startswith("fit_non_convergence") for r in reasons) else (
        "warn" if reasons else "pass"
    )
    return GateResult(status=status, reasons=reasons)


def _route(gate: GateResult, residual_verdict: str, vs_leader: dict) -> tuple[str, str]:
    """Typed-grounded router. Returns (verdict, next_move)."""
    if gate.status == "fail":
        return ("shelve", "drop_lever_unidentifiable")
    if residual_verdict == "unknown":
        # assessment.md is missing — agent skipped diagnosis. Different route
        # than 'actually at noise floor'.
        return ("keep", "run_assessment_first")
    if residual_verdict.startswith("structure_detected:autocorr"):
        return ("keep", "climb_to_rung_1")
    if residual_verdict.startswith("structure_detected:signed_bias"):
        return ("keep", "try_per_platform_bias_correction")
    if residual_verdict.startswith("structure_detected:feature_corr"):
        feat = residual_verdict.split(":", 2)[-1]
        return ("keep", f"add_lever_{feat}")
    if (residual_verdict == "noise_floor"
            and vs_leader["yaw_delta_pct"] < 0
            and vs_leader["signal_above_noise"]):
        return ("promote_to_leader", "stop_and_ship")
    if residual_verdict == "noise_floor":
        return ("keep", "try_residual_learner")
    return ("keep", "keep_iterating_on_this_lever")


# ---------------------------------------------------------------------------
# Tree + registries
# ---------------------------------------------------------------------------

def _read_tree(template_root: Path) -> dict:
    tree_path = template_root / "TREE.json"
    if not tree_path.exists():
        return {"schema_version": 1, "nodes": []}
    return json.loads(tree_path.read_text())


def _write_tree(template_root: Path, tree: dict) -> None:
    (template_root / "TREE.json").write_text(json.dumps(tree, indent=2) + "\n")


def _branch_depth(tree: dict, model_name: str) -> int:
    """Count consecutive ancestors of model_name with warn/fail gate status."""
    by_name = {n["name"]: n for n in tree["nodes"]}
    depth = 0
    cur = by_name.get(model_name)
    while cur and cur.get("gate_status") in ("warn", "fail"):
        depth += 1
        parent = cur.get("parent")
        if not parent or parent == "v1":
            break
        cur = by_name.get(parent)
    return depth


def _find_leader(tree: dict, exclude_name: str | None = None) -> dict | None:
    """Return the current leader node (lowest pooled yaw RMSE among
    promote_to_leader / shipped). Returns None if there isn't one yet."""
    leaders = [
        n for n in tree["nodes"]
        if n.get("verdict") in ("promote_to_leader", "shipped")
        and n.get("name") != exclude_name
    ]
    if not leaders:
        return None
    return min(leaders, key=lambda n: n["pooled_yaw_rmse"])


def _score_named_node(template_root: Path, node_name: str) -> dict | None:
    """Load and CV-score the predict.py for a named node. Returns None if the
    bundle isn't on disk (e.g. the agent ran iterate on a deleted dir)."""
    bundle = _models_root(template_root) / node_name
    if not (bundle / "predict.py").exists():
        return None
    predict_fn = _load_predict(bundle)
    return _cv_score(predict_fn, template_root)


# ---------------------------------------------------------------------------
# iterate() — the public entry
# ---------------------------------------------------------------------------

def iterate(model_dir: str | Path, parent: str | None = None, rung: str | None = None) -> dict:
    model_dir = _resolve_model_dir(model_dir)
    template_root = _find_template_root(model_dir) or _template_root()
    _ensure_root_on_syspath(template_root)

    # Pre-gates (cheap; fire before scoring).
    _require_differs_section(model_dir)
    notes = _load_notes(model_dir)
    parent = parent or notes["parent"]
    rung = rung or notes["rung"]

    predict_fn = _load_predict(model_dir)

    # Idempotence smoke — fail fast if predict is non-deterministic.
    try:
        sample_paths = sorted(
            (template_root / "data" / "sim" / "segments").rglob("sim.csv")
        )[:IDEMPOTENCE_SMOKE_SEGMENTS]
        _idempotence_smoke(predict_fn, sample_paths, template_root=template_root)
    except NonIdempotentPredictError:
        raise
    except Exception:
        pass

    # Compose with assess-candidate-model.
    residual_verdict = _run_assess(model_dir, template_root)

    # Real CV-score the candidate.
    cand_cv = _cv_score(predict_fn, template_root)

    # Score V1 baseline.
    from code import v1_baseline  # type: ignore
    v1_cv = _cv_score(v1_baseline.predict_v1, template_root)
    vs_v1 = _diff(cand_cv, v1_cv)

    # Resolve parent CV: actually score the parent (was: silently used leader_cv).
    tree = _read_tree(template_root)
    if parent == "v1":
        parent_cv = v1_cv
    else:
        parent_cv = _score_named_node(template_root, parent)
        if parent_cv is None:
            # Parent bundle missing on disk. Fall back to V1 for the diff but
            # flag in the gate reasons so it's not silent.
            parent_cv = v1_cv
    vs_parent = _diff(cand_cv, parent_cv)

    # Leader (uses _models_root → v1/v2 aware).
    leader_node = _find_leader(tree, exclude_name=model_dir.name)
    if leader_node is not None:
        leader_cv = _score_named_node(template_root, leader_node["name"]) or v1_cv
    else:
        leader_cv = v1_cv
    vs_leader = _diff(cand_cv, leader_cv)

    fit_diagnostics = None
    fit_log = model_dir / "fit_diagnostics.json"
    if fit_log.exists():
        fit_diagnostics = json.loads(fit_log.read_text())

    gate = _run_gate(cand_cv, vs_parent, fit_diagnostics)
    if parent != "v1" and parent_cv is v1_cv:
        gate.reasons.append("parent-bundle-missing")
    verdict, next_move = _route(gate, residual_verdict, vs_leader)

    # Stagnation soft-refusal.
    stagnation = (
        _branch_depth(tree, parent) >= STAGNATION_BRANCH_LEN
        if parent != "v1" else False
    )
    if stagnation:
        next_move = "compact_and_restart"
        if verdict == "promote_to_leader":
            verdict = "keep"
            gate.reasons.append("stagnant-branch-cannot-promote")

    node_id = f"n{len(tree['nodes']):04d}"
    node = {
        "id": node_id,
        "name": model_dir.name,
        "dir_rel": _relative_dir(template_root, model_dir),
        "parent": parent,
        "rung": rung,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "pooled_yaw_rmse": cand_cv["pooled"]["yaw_rmse"],
        "pooled_yaw_std":  cand_cv["pooled"].get("yaw_std", 0.0),
        "pooled_cte_rmse": cand_cv["pooled"]["cte_rmse"],
        "pooled_cte_std":  cand_cv["pooled"].get("cte_std", 0.0),
        "vs_v1_yaw_pct": vs_v1["yaw_delta_pct"],
        "vs_v1_cte_pct": vs_v1["cte_delta_pct"],
        "gate_status": gate.status,
        "gate_reasons": gate.reasons,
        "residual_verdict": residual_verdict,
        "verdict": verdict,
        "next_move": next_move,
    }
    tree["nodes"].append(node)
    _write_tree(template_root, tree)

    _append_models_md(template_root, node)
    _append_experiments_md(template_root, node)

    return {
        "dev_cv": cand_cv,
        "vs_parent": vs_parent,
        "vs_v1": vs_v1,
        "vs_leader": vs_leader,
        "gate": {"status": gate.status, "reasons": gate.reasons},
        "verdict": verdict,
        "next_move": next_move,
        "stagnation": stagnation,
        "tree_node_id": node_id,
    }


def _append_models_md(template_root: Path, node: dict) -> None:
    path = template_root / "MODELS.md"
    block = (
        f"\n## {node['name']}\n"
        f"- dir: {node['dir_rel']}/\n"
        f"- parent: {node['parent']}\n"
        f"- rung: {node['rung']}\n"
        f"- structure: {'refines-v1' if node['rung'] == '0' else 'differs-from-v1'}\n"
        f"- status: {node['verdict']}\n"
        f"- pooled-yaw-rmse-dev: {node['pooled_yaw_rmse']:.6f} ± {node['pooled_yaw_std']:.6f}\n"
        f"- pooled-cte-rmse-dev: {node['pooled_cte_rmse']:.3f} ± {node['pooled_cte_std']:.3f}\n"
        f"- vs-v1: yaw {node['vs_v1_yaw_pct']:+.1f}%, CTE {node['vs_v1_cte_pct']:+.1f}%\n"
        f"- gate: {node['gate_status']} ({', '.join(node['gate_reasons']) or 'clean'})\n"
        f"- next: {node['next_move']}\n"
    )
    with path.open("a") as f:
        f.write(block)


def _append_experiments_md(template_root: Path, node: dict) -> None:
    path = template_root / "EXPERIMENTS.md"
    entry = (
        f"\n### {node['timestamp']} — {node['name']}\n"
        f"- Parent: {node['parent']}  |  Rung: {node['rung']}\n"
        f"- Dev CV: yaw {node['pooled_yaw_rmse']:.6f} ± {node['pooled_yaw_std']:.6f}, "
        f"CTE {node['pooled_cte_rmse']:.3f} ± {node['pooled_cte_std']:.3f}\n"
        f"- vs V1: yaw {node['vs_v1_yaw_pct']:+.1f}%, CTE {node['vs_v1_cte_pct']:+.1f}%\n"
        f"- Gate: {node['gate_status']} — {', '.join(node['gate_reasons']) or 'clean'}\n"
        f"- Residual: {node['residual_verdict']}\n"
        f"- Verdict: {node['verdict']}  →  next: {node['next_move']}\n"
    )
    with path.open("a") as f:
        f.write(entry)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("model_dir")
    p.add_argument("--parent", default=None)
    p.add_argument("--rung", default=None)
    args = p.parse_args()
    result = iterate(args.model_dir, parent=args.parent, rung=args.rung)
    print(json.dumps(result, indent=2, default=str))
