"""One-shot tree-search iteration step. Model-shape-agnostic.

Runs the verifier gate against a candidate model bundle and logs the result
across TREE.json, MODELS.md, EXPERIMENTS.md. See SKILL.md for the contract.

This is a SKELETON. The gate and routing logic are intentionally small so
agents can extend them per cohort discovery.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

# Repo-relative imports — adjust if your layout differs.
TEMPLATE_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TEMPLATE_ROOT))

from skills.score_model.score import score, format_summary  # noqa: E402

CV_K = 5
NOISE_MULTIPLIER = 1.0  # signal must beat parent by > NOISE_MULTIPLIER * pooled CV std
STAGNATION_BRANCH_LEN = 3
DEV_TRAIN_GAP_WARN = 0.30


@dataclass
class GateResult:
    status: str  # "pass" | "warn" | "fail"
    reasons: list[str] = field(default_factory=list)


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


def _cv_score(predict_fn, k: int = CV_K) -> dict:
    """Score the candidate with k-fold route-grouped CV on the dev split.

    SKELETON: actual k-fold loop should pull route IDs from data/sim/segments/
    and partition with the make-train-dev-split utility (route-grouped, no leakage).
    Returns mean ± std per platform + pooled.
    """
    # Single-fold placeholder — extend to real k-fold using make-train-dev-split.
    result = score(predict_fn)
    pooled = {
        "yaw_rmse": result["yaw_rate_rmse"],
        "yaw_std": 0.0,  # populated by real k-fold
        "cte_rmse": result["cte_rmse"],
        "cte_std": 0.0,
    }
    return {"pooled": pooled, "per_platform": result["per_platform"], "raw": result}


def _diff(candidate: dict, baseline: dict) -> dict:
    yaw_pct = 100.0 * (candidate["pooled"]["yaw_rmse"] - baseline["pooled"]["yaw_rmse"]) / baseline["pooled"]["yaw_rmse"]
    cte_pct = 100.0 * (candidate["pooled"]["cte_rmse"] - baseline["pooled"]["cte_rmse"]) / baseline["pooled"]["cte_rmse"]
    noise = candidate["pooled"]["yaw_std"] + baseline["pooled"]["yaw_std"]
    signal_above_noise = abs(yaw_pct) > 100.0 * NOISE_MULTIPLIER * noise / max(baseline["pooled"]["yaw_rmse"], 1e-9)
    return {"yaw_delta_pct": yaw_pct, "cte_delta_pct": cte_pct, "signal_above_noise": signal_above_noise}


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
    """Typed-grounded router. Returns (verdict, next_move).

    Extend with cohort-discovered patterns. Each route MUST be verifiable from
    the gate + residual output — do not infer beyond what we can check.
    """
    if gate.status == "fail":
        return ("shelve", "drop_lever_unidentifiable")
    if residual_verdict.startswith("structure_detected:autocorr"):
        return ("keep", "climb_to_rung_1")
    if residual_verdict.startswith("structure_detected:signed_bias"):
        return ("keep", "try_per_platform_bias_correction")
    if residual_verdict.startswith("structure_detected:feature_corr"):
        feat = residual_verdict.split(":", 2)[-1]
        return ("keep", f"add_lever_{feat}")
    if residual_verdict == "noise_floor" and vs_leader["yaw_delta_pct"] < 0 and vs_leader["signal_above_noise"]:
        return ("promote_to_leader", "stop_and_ship")
    if residual_verdict == "noise_floor":
        return ("keep", "try_residual_learner")
    return ("keep", "keep_iterating_on_this_lever")


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


def iterate(model_dir: str | Path, parent: str | None = None, rung: str | None = None) -> dict:
    model_dir = Path(model_dir).resolve()
    template_root = model_dir.parent.parent
    notes = _load_notes(model_dir)
    parent = parent or notes["parent"]
    rung = rung or notes["rung"]

    predict_fn = _load_predict(model_dir)
    cand_cv = _cv_score(predict_fn)

    # Score V1 + parent + leader for diffs.
    from code import v1_baseline  # type: ignore
    v1_cv = _cv_score(v1_baseline.predict_v1)
    vs_v1 = _diff(cand_cv, v1_cv)

    tree = _read_tree(template_root)
    leader_name = max(
        (n for n in tree["nodes"] if n.get("verdict") in ("promote_to_leader", "shipped")),
        key=lambda n: -n["pooled_yaw_rmse"],
        default=None,
    )
    if leader_name and leader_name["name"] != model_dir.name:
        leader_predict = _load_predict(template_root / "models" / leader_name["name"])
        leader_cv = _cv_score(leader_predict)
    else:
        leader_cv = v1_cv
    vs_leader = _diff(cand_cv, leader_cv)
    vs_parent = vs_v1 if parent == "v1" else _diff(cand_cv, leader_cv)

    # Read residual-structure verdict from assessment.md if present, else a noop string.
    assessment = model_dir / "assessment.md"
    residual_verdict = "noise_floor"
    if assessment.exists():
        for line in assessment.read_text().splitlines():
            if line.lower().startswith("- residual_verdict:"):
                residual_verdict = line.split(":", 1)[1].strip()

    fit_diagnostics = None
    fit_log = model_dir / "fit_diagnostics.json"
    if fit_log.exists():
        fit_diagnostics = json.loads(fit_log.read_text())

    gate = _run_gate(cand_cv, vs_parent, fit_diagnostics)
    verdict, next_move = _route(gate, residual_verdict, vs_leader)

    # Stagnation check: 3 consecutive warn/fail nodes on this branch.
    stagnation = _branch_depth(tree, parent) >= STAGNATION_BRANCH_LEN if parent != "v1" else False
    if stagnation:
        next_move = "compact_and_restart"

    node_id = f"n{len(tree['nodes']):04d}"
    node = {
        "id": node_id,
        "name": model_dir.name,
        "parent": parent,
        "rung": rung,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "pooled_yaw_rmse": cand_cv["pooled"]["yaw_rmse"],
        "pooled_cte_rmse": cand_cv["pooled"]["cte_rmse"],
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
        f"- dir: models/{node['name']}/\n"
        f"- parent: {node['parent']}\n"
        f"- rung: {node['rung']}\n"
        f"- structure: {'refines-v1' if node['rung'] == '0' else 'differs-from-v1'}\n"
        f"- status: {node['verdict']}\n"
        f"- pooled-yaw-rmse-dev: {node['pooled_yaw_rmse']:.6f}\n"
        f"- pooled-cte-rmse-dev: {node['pooled_cte_rmse']:.3f}\n"
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
        f"- Dev CV: yaw {node['pooled_yaw_rmse']:.6f}, CTE {node['pooled_cte_rmse']:.3f}\n"
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
