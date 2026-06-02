"""Mechanical gates shared by skills/iterate and skills/pre-flight-final-model.

Each gate is a pure function over a model bundle. Returns (ok, detail). Never
raises on a per-check failure — the caller decides how to surface the result
(fail row in preflight, gate_reason in iterate).

Gates live here rather than under a hyphenated `skills/` dir so they can be
imported as a plain Python module from both consumers.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

# Per-platform additive-bias-like fields. Any of these with a non-trivial
# magnitude triggers the route-CV-σ requirement (m4-cohort-findings.md §6,
# §9 — agent-07 shipped per-platform bias on an i.i.d. holdout; the bias
# sign was an artefact of which routes landed in the training split).
BIAS_FIELDS: tuple[str, ...] = (
    "bias",
    "bias_rad",
    "delta_bias",
    "delta_bias_rad",
    "delta0",
    "d0",
    "off",
    "delta_offset",
)

# Sibling fields that prove the bias was selected under route-grouped CV.
# Either form is accepted: a single combined σ, or per-KPI σ.
ROUTE_CV_SIGMA_FIELDS: tuple[str, ...] = (
    "route_cv_sigma",
    "route_cv_sigma_yaw",
    "route_cv_sigma_cte",
    "route_cv_sigma_bias",
)

BIAS_MAGNITUDE_FLOOR = 1e-6  # smaller than this counts as "effectively zero".


def _is_real_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def find_bias_violations(coeffs: dict) -> list[str]:
    """Scan a parsed coeffs.json dict for bias terms without route_cv_sigma.

    Returns a list of human-readable violation strings (one per offending
    platform); empty list means the gate passes.

    A coeffs.json may be flat ({"FORD_F_150_LIGHTNING_MK1": {...}, ...}) or
    nested under a top-level "coeffs" / "platforms" key. Both are tolerated.
    """
    if not isinstance(coeffs, dict):
        return []
    # Normalise: pull the per-platform map out of common wrappers.
    if "coeffs" in coeffs and isinstance(coeffs["coeffs"], dict):
        per_platform = coeffs["coeffs"]
    elif "platforms" in coeffs and isinstance(coeffs["platforms"], dict):
        per_platform = coeffs["platforms"]
    else:
        per_platform = coeffs

    violations: list[str] = []
    for platform, entry in per_platform.items():
        if not isinstance(entry, dict):
            continue
        if not platform or not isinstance(platform, str):
            continue
        # Find a bias-like lever with non-trivial magnitude.
        bias_field = None
        bias_value = None
        for f in BIAS_FIELDS:
            v = entry.get(f)
            if _is_real_number(v) and abs(v) > BIAS_MAGNITUDE_FLOOR:
                bias_field = f
                bias_value = v
                break
        if bias_field is None:
            continue
        has_route_cv = any(s in entry for s in ROUTE_CV_SIGMA_FIELDS)
        if not has_route_cv:
            violations.append(
                f"{platform}.{bias_field}={bias_value:+.5f} (no route_cv_sigma sibling)"
            )
    return violations


def check_bias_without_route_cv(coeffs_path: Path | str) -> tuple[bool, str]:
    """Hard gate: per-platform bias terms must carry a `route_cv_sigma` sibling.

    Why this is a refuse, not a warn: cohort §6 + §9 document that subset fits
    flip the Lightning bias sign. The agent-07 mode (m4.v1 cohort, +44.6% yaw)
    was an i.i.d. holdout bias fit that the template's warning didn't block.

    Parameters
    ----------
    coeffs_path : path to coeffs.json (usually `models/<name>/coeffs.json` or
        `final-model/coeffs.json`).

    Returns
    -------
    (ok, detail) where ok=True means: no bias terms, OR every bias term has a
    `route_cv_sigma`-family sibling field that proves it was selected under
    route-grouped CV.
    """
    coeffs_path = Path(coeffs_path)
    if not coeffs_path.exists():
        return True, "no coeffs.json — gate vacuous (no declared coefficients)"
    try:
        coeffs = json.loads(coeffs_path.read_text(encoding="utf-8"))
    except Exception as e:
        # Don't fail the bias gate on a JSON parse error — that's a separate
        # contract surface owned by manifest_parses / coeffs schema checks.
        return True, f"coeffs.json unparseable ({type(e).__name__}); bias gate skipped"
    violations = find_bias_violations(coeffs)
    if not violations:
        return True, "no per-platform bias terms (or all carry route_cv_sigma)"
    detail = (
        "per-platform bias declared without route_cv_sigma: "
        + "; ".join(violations)
        + ". See references/m4-cohort-findings.md §6 + §9 — agent-07 (m4.v1) "
        "shipped a Lightning bias of -0.00411 selected on an i.i.d. holdout; "
        "the sign was an artefact of which routes landed in the training split. "
        "Fix: run skills/score-model/cv.py:score_cv on the bias-fitting step "
        "and write the σ back into coeffs.json under each platform with a "
        "bias term (field name `route_cv_sigma` or `route_cv_sigma_yaw`)."
    )
    return False, detail


def _iterate_history_count(experiments_md_path: Path) -> int:
    """Count append-only entries in EXPERIMENTS.md written by skills/iterate.

    The iterate skill writes one entry per call in the form:

        ### <timestamp> — <name>
        - Parent: <…>  |  Rung: <…>
        - Dev CV: ...

    We count entries whose body contains BOTH the `- Dev CV:` and `- Verdict:`
    lines that only iterate writes. Hand-written EXPERIMENTS.md entries
    (with `- Hypothesis:` / `- Result (dev):`) are not counted — the point
    of this gate is to confirm the iterate verifier ran ≥N times, not that
    the agent typed ≥N markdown blocks.
    """
    if not experiments_md_path.exists():
        return 0
    text = experiments_md_path.read_text(encoding="utf-8")
    # Split on '### ' headings (top-level entry separator iterate writes).
    blocks = text.split("\n### ")
    count = 0
    for b in blocks:
        if "- Dev CV:" in b and "- Verdict:" in b and "- Gate:" in b:
            count += 1
    return count


def check_iterate_history_min(
    experiments_md_path: Path | str,
    *,
    min_calls: int,
) -> tuple[bool, str, int]:
    """Verify EXPERIMENTS.md has ≥ min_calls entries written by iterate.

    Returns (ok, detail, count). This replaces the gameable
    `models_md_has_min_candidates` count: the agent can `touch` model files,
    but every entry counted here required a full iterate gate run.
    """
    n = _iterate_history_count(Path(experiments_md_path))
    if n >= min_calls:
        return True, f"EXPERIMENTS.md has {n} iterate-written entries (>= {min_calls})", n
    return False, (
        f"EXPERIMENTS.md has {n} iterate-written entries; preflight requires "
        f">= {min_calls}. Use skills/iterate/ on each candidate. agent-07 (m4.v1) "
        "shipped one candidate with no MODELS.md iterations and scored +44.6% yaw "
        "(vs the cohort median of +56.2%)."
    ), n


REJECTED_CANDIDATES_HEADER_PATTERNS: tuple[str, ...] = (
    "## Candidates considered and rejected",
    "## Tried and shelved",
    "## Structures I tried",
)


def check_report_cites_rejected(report_md_path: Path | str) -> tuple[bool, str]:
    """REPORT.md must cite at least one rejected candidate by name.

    Looks for one of the rejected/tried/shelved section headers, then verifies
    the section body has at least one bullet that mentions a rejected verdict
    (`shelved` / `rejected` / `did not ship`). The check is intentionally
    fuzzy — we want to encourage the cohort discipline of writing rejected
    candidates down, not to enforce a rigid markdown grammar.
    """
    report_md_path = Path(report_md_path)
    if not report_md_path.exists():
        return False, f"REPORT.md missing at {report_md_path}"
    text = report_md_path.read_text(encoding="utf-8")
    section_text = None
    section_header = None
    for header in REJECTED_CANDIDATES_HEADER_PATTERNS:
        idx = text.find(header)
        if idx == -1:
            continue
        end = text.find("\n## ", idx + len(header))
        section_text = text[idx:end if end != -1 else None]
        section_header = header
        break
    if section_text is None:
        return False, (
            "REPORT.md has no '## Candidates considered and rejected' / "
            "'## Tried and shelved' / '## Structures I tried' section. "
            "Cite at least one candidate that was built but did not ship — "
            "the agent-07 (m4.v1) mode was shipping one candidate with no "
            "comparison."
        )
    body = section_text[len(section_header):]
    if "<" in body and ">" in body and "name" in body.lower():
        # placeholder bullets like `- **<name>**` are not counted
        body = "\n".join(line for line in body.splitlines() if "<name>" not in line.lower() and "<" not in line)
    rejected_marker = any(
        word in body.lower()
        for word in ("shelved", "rejected", "did not ship", "ruled out", "discarded")
    )
    bullets = [ln for ln in body.splitlines() if ln.strip().startswith(("-", "*"))]
    if not bullets:
        return False, (
            f"REPORT.md '{section_header}' section has no bulleted entries. "
            "Add at least one candidate-by-name bullet that did not ship."
        )
    if not rejected_marker:
        return False, (
            f"REPORT.md '{section_header}' section has bullets but none names a "
            "rejected verdict (shelved / rejected / did not ship / ruled out). "
            "The point of the section is to surface the candidate(s) the cohort "
            "should NOT retry."
        )
    return True, f"REPORT.md '{section_header}' cites ≥ 1 rejected candidate."


PARENT_BASELINE_HEADER = "## Parent baseline"
PARENT_BASELINE_ALLOWED = ("v0", "v1", "fresh")


def check_parent_baseline_declared(plan_md_path: Path | str) -> tuple[bool, str]:
    """PLAN.md must declare which baseline its candidates build on, with evidence.

    Looks for a `## Parent baseline` section whose body names one of
    `V0 | V1 | fresh` AND has a non-placeholder evidence line. The
    motivating failure mode is m4.v1 agent-10, which built on V0 (0.01293
    rad/s yaw RMSE) instead of V1 (0.00587), and was 2.2× off the floor
    before any work began.
    """
    plan_md_path = Path(plan_md_path)
    if not plan_md_path.exists():
        return False, f"PLAN.md missing at {plan_md_path}"
    text = plan_md_path.read_text(encoding="utf-8")
    idx = text.find(PARENT_BASELINE_HEADER)
    if idx == -1:
        return False, (
            f"PLAN.md is missing the '{PARENT_BASELINE_HEADER}' section. "
            "Name the baseline candidates build on (V0 | V1 | fresh) plus one "
            "line of evidence. Lock.sh refuses to lock without it; preflight "
            "refuses to ship without it. This catches the m4.v1 agent-10 mode "
            "(built on V0; -17 pp behind the cohort)."
        )
    end = text.find("\n## ", idx + len(PARENT_BASELINE_HEADER))
    body = text[idx:end if end != -1 else None]
    body_lower = body.lower()
    has_choice = any(b in body_lower for b in PARENT_BASELINE_ALLOWED)
    if not has_choice:
        return False, (
            f"'{PARENT_BASELINE_HEADER}' section in PLAN.md does not name a "
            "baseline (V0 / V1 / fresh). Pick one and cite evidence."
        )
    # Reject placeholder-only bodies (e.g. just `<...>` or the template comment).
    non_placeholder = [
        ln for ln in body.splitlines()[1:]  # skip the header line itself
        if ln.strip()
        and not ln.strip().startswith("<!--")
        and "<" not in ln  # rough placeholder filter
        and ln.strip() != PARENT_BASELINE_HEADER.lstrip("#").strip()
    ]
    if len(non_placeholder) < 2:
        return False, (
            f"'{PARENT_BASELINE_HEADER}' section is present but appears to "
            "contain only placeholders. Fill in the choice AND one line of "
            "evidence (V1's yaw RMSE, V0's yaw RMSE, why one is the right floor)."
        )
    return True, f"PLAN.md declares parent baseline with evidence."
