"""Coordinator skill: assess a candidate model against V1 and write assessment.md.

Loads `<model_dir>/predict.py`, runs the standard battery (score / compare-vs-V1 /
residual-structure), writes a populated `<model_dir>/assessment.md`. Treat the
output as a starting point — extend the assessment with model-class-specific
diagnostics inline.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pandas as pd

HERE = Path(__file__).resolve().parent
SKILLS_DIR = HERE.parent
AGENT_DIR = HERE.parents[1]
CODE_DIR = AGENT_DIR / "code"

# Pull sibling skills onto sys.path so we can import their entry points.
for _p in (
    SKILLS_DIR / "score-model",
    SKILLS_DIR / "compare-models",
    SKILLS_DIR / "residual-structure",
    AGENT_DIR / "_shared",
    CODE_DIR,
):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from score import score  # type: ignore  # noqa: E402
from compare import compare, per_platform_summary, top_regressions, top_improvements  # type: ignore  # noqa: E402
from residual_structure import residual_structure  # type: ignore  # noqa: E402


def _load_predict(model_dir: Path):
    """Import predict.py from model_dir; return the predict callable."""
    predict_path = model_dir / "predict.py"
    if not predict_path.exists():
        raise FileNotFoundError(f"no predict.py in {model_dir}")
    # Put model_dir on sys.path so predict.py can import sibling helpers.
    sys.path.insert(0, str(model_dir.resolve()))
    try:
        spec = importlib.util.spec_from_file_location(
            f"_assess_predict_{abs(hash(str(predict_path)))}", str(predict_path)
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"could not build import spec for {predict_path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        try:
            sys.path.remove(str(model_dir.resolve()))
        except ValueError:
            pass
    fn = getattr(module, "predict", None)
    if fn is None or not callable(fn):
        raise AttributeError(f"{predict_path} has no callable `predict`")
    return fn


def _load_v1():
    from v1_baseline import predict_v1  # type: ignore
    return predict_v1


def _safe_pct(numer: float, denom: float) -> float:
    if denom == 0 or denom != denom:  # NaN-safe
        return float("nan")
    return 100.0 * (denom - numer) / denom


def assess(
    model_dir: str | Path,
    segment_paths: list | None = None,
    write_assessment: bool = True,
) -> dict[str, Any]:
    """Assess a candidate model. Returns a result dict; writes assessment.md."""
    model_dir = Path(model_dir)
    if not model_dir.is_dir():
        raise NotADirectoryError(f"{model_dir} is not a directory")

    candidate = _load_predict(model_dir)
    v1 = _load_v1()

    # --- score candidate -----------------------------------------------------
    score_cand = score(candidate, segment_paths=segment_paths)
    score_v1 = score(v1, segment_paths=segment_paths)

    # --- compare per-segment vs V1 -------------------------------------------
    diff_df = compare(
        candidate, v1, segment_paths=segment_paths,
        name_a=model_dir.name, name_b="v1",
    )
    pp_table = per_platform_summary(diff_df, name_a=model_dir.name, name_b="v1")
    top_regr = top_regressions(diff_df, metric="cte_delta", n=5)
    top_impr = top_improvements(diff_df, metric="cte_delta", n=5)

    # --- residual structure of candidate -------------------------------------
    rs = residual_structure(candidate, segment_paths=segment_paths)

    # --- summarise -----------------------------------------------------------
    pooled_cand_yaw = score_cand.get("yaw_rate_rmse")
    pooled_cand_cte = score_cand.get("cte_rmse")
    pooled_v1_yaw = score_v1.get("yaw_rate_rmse")
    pooled_v1_cte = score_v1.get("cte_rmse")

    result: dict[str, Any] = {
        "model_dir": str(model_dir),
        "pooled": {
            "yaw_rate_rmse": pooled_cand_yaw,
            "cte_rmse": pooled_cand_cte,
        },
        "vs_v1": {
            "v1_yaw_rate_rmse": pooled_v1_yaw,
            "v1_cte_rmse": pooled_v1_cte,
            "delta_yaw_pct": _safe_pct(pooled_cand_yaw, pooled_v1_yaw),
            "delta_cte_pct": _safe_pct(pooled_cand_cte, pooled_v1_cte),
        },
        "per_platform": score_cand.get("per_platform", {}),
        "per_platform_vs_v1": pp_table.to_dict("records") if not pp_table.empty else [],
        "top_regressions": top_regr.to_dict("records") if not top_regr.empty else [],
        "top_improvements": top_impr.to_dict("records") if not top_impr.empty else [],
        "residual_structure": rs,
    }

    if write_assessment:
        result["assessment_path"] = _write_assessment_md(model_dir, result)

    return result


def _write_assessment_md(model_dir: Path, r: dict) -> str:
    out = model_dir / "assessment.md"
    lines: list[str] = []
    lines.append(f"# assessment — `{model_dir.name}`")
    lines.append("")
    lines.append("> Auto-stamped by `skills/assess-candidate-model`. Extend with")
    lines.append("> model-class-specific diagnostics inline.")
    lines.append("")
    lines.append("## Headline (pooled, candidate vs V1)")
    lines.append("")
    p = r["pooled"]
    v = r["vs_v1"]
    lines.append(f"- candidate: yaw_rmse = {p['yaw_rate_rmse']:.6f} rad/s,"
                 f" cte_rmse = {p['cte_rmse']:.3f} m")
    lines.append(f"- V1:        yaw_rmse = {v['v1_yaw_rate_rmse']:.6f} rad/s,"
                 f" cte_rmse = {v['v1_cte_rmse']:.3f} m")
    lines.append(f"- Δ vs V1:   yaw {_fmt_pct(v['delta_yaw_pct'])},"
                 f" cte {_fmt_pct(v['delta_cte_pct'])}")
    lines.append("")
    lines.append("## Per-platform vs V1")
    lines.append("")
    if r["per_platform_vs_v1"]:
        cols = list(r["per_platform_vs_v1"][0].keys())
        lines.append("| " + " | ".join(cols) + " |")
        lines.append("|" + "|".join(["---"] * len(cols)) + "|")
        for row in r["per_platform_vs_v1"]:
            lines.append("| " + " | ".join(_fmt_cell(row[c]) for c in cols) + " |")
    else:
        lines.append("_(no per-platform rows — compare returned empty)_")
    lines.append("")
    lines.append("## Top CTE improvements (5 best segments vs V1)")
    lines.append("")
    lines.append(_render_segment_rows(r["top_improvements"]))
    lines.append("")
    lines.append("## Top CTE regressions (5 worst segments vs V1)")
    lines.append("")
    lines.append(_render_segment_rows(r["top_regressions"]))
    lines.append("")
    lines.append("## Residual-structure verdict (per platform)")
    lines.append("")
    pp = r["residual_structure"].get("per_platform", {})
    for plat, info in pp.items():
        verdict = info.get("verdict", "?")
        reason = info.get("reason", "")
        lines.append(f"- **{plat}**: `{verdict}` — {reason}")
    if not pp:
        lines.append("_(no per-platform residual structure data)_")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append("**FILL IN**: keep / shelve, with one-paragraph reason. If shelving,")
    lines.append("name what failed (under-parameterised? wrong residual attacked?")
    lines.append("integrator unstable?) — that's what makes the assessment useful to")
    lines.append("the next agent.")
    lines.append("")
    lines.append("## Model-class-specific diagnostics")
    lines.append("")
    lines.append("**FILL IN**: extend the standard battery with diagnostics that fit")
    lines.append("this model's shape (slip-angle plot for dynamic ST, feature-importance")
    lines.append("for residual learners, integrator-stability check, etc.).")
    lines.append("")

    out.write_text("\n".join(lines), encoding="utf-8")
    return str(out)


def _fmt_pct(pct: float) -> str:
    if pct != pct:  # NaN
        return "n/a"
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct:.2f}%"


def _fmt_cell(v) -> str:
    if isinstance(v, float):
        if v != v:
            return "n/a"
        return f"{v:.4f}"
    return str(v)


def _render_segment_rows(rows: list) -> str:
    if not rows:
        return "_(no rows)_"
    cols = list(rows[0].keys())
    out = ["| " + " | ".join(cols) + " |",
           "|" + "|".join(["---"] * len(cols)) + "|"]
    for row in rows:
        out.append("| " + " | ".join(_fmt_cell(row[c]) for c in cols) + " |")
    return "\n".join(out)
