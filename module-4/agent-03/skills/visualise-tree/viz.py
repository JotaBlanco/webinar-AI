"""Render TREE.json as ASCII / markdown / PNG. See SKILL.md."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

GLYPH = {"pass": "✓", "warn": "△", "fail": "✗"}
V1_NODE = {"id": "v1", "name": "v1", "parent": None, "rung": "0",
           "pooled_yaw_rmse": 0.005874, "pooled_cte_rmse": 56.81,
           "vs_v1_yaw_pct": 0.0, "vs_v1_cte_pct": 0.0,
           "gate_status": "pass", "gate_reasons": [], "verdict": "leader",
           "residual_verdict": "—", "next_move": "—"}


def visualise_tree(tree_path: str | Path | None = None, format: str = "ascii",
                   highlight: str | None = None) -> str | Path:
    tree_path = Path(tree_path or _default_tree_path())
    tree = json.loads(tree_path.read_text()) if tree_path.exists() else {"nodes": []}
    nodes = [V1_NODE] + list(tree.get("nodes", []))
    by_name = {n["name"]: n for n in nodes}
    children = defaultdict(list)
    for n in nodes:
        p = n.get("parent")
        if p and p in by_name:
            children[p].append(n)
    leader = highlight or _current_leader(nodes)

    if format == "ascii":
        lines: list[str] = []
        _ascii_node(by_name.get("v1", V1_NODE), children, lines, prefix="", is_last=True, leader=leader)
        return "\n".join(lines)
    if format == "markdown":
        return _markdown(by_name.get("v1", V1_NODE), children, leader, depth=0)
    if format == "png":
        return _png(nodes, children, leader)
    raise ValueError(f"unknown format: {format}")


def _ascii_node(node, children, lines, prefix, is_last, leader):
    rung = _fmt_rung(node["rung"])
    yaw = node["pooled_yaw_rmse"]
    delta = f"{node['vs_v1_yaw_pct']:+.1f}%" if node["name"] != "v1" else ""
    glyph = GLYPH.get(node["gate_status"], "?")
    reasons = f"({len(node['gate_reasons'])})" if node["gate_reasons"] else ""
    verdict = node["verdict"]
    star = " ★" if node["name"] == leader else ""
    connector = "└─ " if is_last else "├─ "
    line = f"{prefix}{connector if prefix else ''}{node['name']}  {rung}  {yaw:.6f} {delta} {glyph}{reasons} {verdict}{star}".rstrip()
    lines.append(line)
    kids = children.get(node["name"], [])
    new_prefix = prefix + ("   " if is_last else "│  ")
    for i, k in enumerate(kids):
        _ascii_node(k, children, lines, new_prefix, i == len(kids) - 1, leader)


def _markdown(node, children, leader, depth: int) -> str:
    indent = "  " * depth
    rung = _fmt_rung(node["rung"])
    star = " **(leader)**" if node["name"] == leader else ""
    line = (
        f"{indent}- [{node['name']}](models/{node['name']}/assessment.md) "
        f"{rung} `{node['pooled_yaw_rmse']:.6f}` ({node['vs_v1_yaw_pct']:+.1f}% vs V1) "
        f"{GLYPH.get(node['gate_status'], '?')} {node['verdict']}{star}"
    )
    out = [line]
    for k in children.get(node["name"], []):
        out.append(_markdown(k, children, leader, depth + 1))
    return "\n".join(out)


def _png(nodes, children, leader) -> Path:
    try:
        import matplotlib.pyplot as plt  # noqa: F401
    except ImportError as e:
        raise RuntimeError("matplotlib required for PNG output") from e
    # Skeleton — extend with networkx-based layout.
    out = Path("_artifacts")
    out.mkdir(exist_ok=True)
    target = out / "tree.png"
    # ...layout + draw — left as an extension hook.
    target.write_text("PNG rendering not implemented in skeleton")
    return target


def _fmt_rung(rung: str) -> str:
    return {"0": "R0", "1": "R1", "2": "R2", "3": "R3", "orthogonal": "ORTH"}.get(str(rung), "R?")


def _current_leader(nodes):
    leaders = [n for n in nodes if n.get("verdict") in ("promote_to_leader", "shipped", "leader")]
    if not leaders:
        return "v1"
    return min(leaders, key=lambda n: n["pooled_yaw_rmse"])["name"]


def _default_tree_path() -> Path:
    return Path(__file__).resolve().parents[2] / "TREE.json"


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--format", default="ascii", choices=["ascii", "markdown", "png"])
    p.add_argument("--highlight", default=None)
    args = p.parse_args()
    print(visualise_tree(format=args.format, highlight=args.highlight))
