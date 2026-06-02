"""Typed-grounded router. Emits one route from a fixed set, only when the
precondition is mechanically verifiable from the gate output. See SKILL.md."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Route:
    name: str
    confidence: str
    rationale: str
    cohort_precedent: str | None = None


BIAS_RAD_S_THRESHOLD = 0.0005
COHORT_REFS = "references/m4-cohort-findings.md"


def critique(gate_output: dict, residual_verdict: str, cohort_hint: bool = True) -> dict:
    gate = gate_output.get("gate", {})
    vs_leader = gate_output.get("vs_leader", {})
    vs_parent = gate_output.get("vs_parent", {})
    stagnation = gate_output.get("stagnation", False)

    # Stagnation has highest priority — preempt further routing.
    if stagnation:
        return Route(
            name="compact_and_restart",
            confidence="high",
            rationale="Branch depth ≥3 consecutive warn/fail nodes; context-rot risk dominates further iteration value.",
            cohort_precedent=None,
        ).__dict__

    reasons = set(gate.get("reasons", []))
    if any(r.startswith("fit_stuck_on_bound:") or r.startswith("fit_co_collapse:") for r in reasons):
        param = next(
            (r.split(":", 1)[1] for r in reasons if r.startswith(("fit_stuck_on_bound:", "fit_co_collapse:"))),
            "unknown",
        )
        return Route(
            name=f"drop_lever_{param}",
            confidence="high",
            rationale=f"Fit diagnostic flagged {param}; lever is not identifiable from this data.",
            cohort_precedent=f"{COHORT_REFS} §3",
        ).__dict__

    if residual_verdict.startswith("structure_detected:signed_bias"):
        platform = residual_verdict.split(":", 2)[-1] if residual_verdict.count(":") >= 2 else ""
        return Route(
            name="try_per_platform_bias_correction",
            confidence="high",
            rationale=f"Signed bias dominates {platform or 'platform'} residual; smallest possible structural delta.",
            cohort_precedent=f"{COHORT_REFS} §2" if cohort_hint else None,
        ).__dict__

    if residual_verdict.startswith("structure_detected:feature_corr"):
        parts = residual_verdict.split(":")
        feat = parts[-1] if len(parts) >= 3 else "unknown_feature"
        return Route(
            name=f"add_lever_{feat}",
            confidence="medium",
            rationale=f"Residual correlates with {feat}; consider adding as a lever if it's in the allowlist.",
            cohort_precedent=None,
        ).__dict__

    if residual_verdict.startswith("structure_detected:autocorr"):
        return Route(
            name="climb_to_rung_1",
            confidence="low",
            rationale=(
                "Short-lag autocorrelation suggests transient dynamics state. "
                "Use _shared/rung1_starter.py and FIT (do not fix) C_αf, C_αr, Iz — "
                "every cohort attempt that used carParams values failed."
            ),
            cohort_precedent=f"{COHORT_REFS} §1, §7" if cohort_hint else None,
        ).__dict__

    if residual_verdict == "noise_floor" and vs_leader.get("yaw_delta_pct", 0) < 0 and vs_leader.get("signal_above_noise"):
        return Route(
            name="stop_and_ship",
            confidence="high",
            rationale="Residual at noise floor; beats current leader on dev CV by > σ.",
            cohort_precedent=None,
        ).__dict__

    if residual_verdict == "noise_floor" and cohort_hint:
        return Route(
            name="try_residual_learner",
            confidence="high",
            rationale=(
                "Residual at noise floor on physics levers but headroom remains on dev. "
                "Ridge or gradient-boosted head on V1 residual reliably wins +1-5% CTE."
            ),
            cohort_precedent=f"{COHORT_REFS} §4",
        ).__dict__

    return Route(
        name="keep_iterating_on_this_lever",
        confidence="low",
        rationale="No precondition for a stronger route is met; refit or re-parameterize the current lever.",
        cohort_precedent=None,
    ).__dict__


if __name__ == "__main__":
    import json
    import sys
    gate_output = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {"gate": {"status": "warn", "reasons": []}}
    residual = sys.argv[2] if len(sys.argv) > 2 else "noise_floor"
    print(json.dumps(critique(gate_output, residual), indent=2))
