"""Canonical eval runner for raw-agent-06's favourite model (v4_per_platform_kus).

Reconstructs the agent's v4 prediction equation from REPORT + tools/score.py:
- Per-segment steering bias subtraction
- Steady-state single-track: psi_dot = v*tan(delta_eff) / (L + scale*K_us*v^2)
- First-order steering lag tau=0.05s on delta
- Per-platform K_us scale (Mach-E 0.5x, F-150 3.0x)
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI")
SIM = ROOT / "data" / "sim" / "segments"
OUT_JSON = ROOT / "raw-model/idea-01/_grade/20260527-164838/canonical/raw-agent-06.json"

ST_BY_PLATFORM = {
    "FORD_MUSTANG_MACH_E_MK1": dict(
        m=2336.0, l_f=1.3130, l_r=1.671, C_f=286_551.0, C_r=355_912.0, L=2.984,
        kus_scale=0.5,
    ),
    "FORD_F_150_LIGHTNING_MK1": dict(
        m=3084.0, l_f=1.628, l_r=2.072, C_f=378_307.0, C_r=469_878.0, L=3.70,
        kus_scale=3.0,
    ),
}

PLATFORM_GLOBS = [
    ("FORD_MUSTANG_MACH_E_MK1", "FORD_MUSTANG_MACH_E_MK1"),
    ("FORD_F_150_LIGHTNING_MK1", "FORD_F_150_LIGHTNING_MK1"),
]


def k_us(p):
    return (p["m"] / p["L"]) * (p["l_r"] / p["C_f"] - p["l_f"] / p["C_r"])


def estimate_bias(t, delta, v, a_lat, yaw):
    mask = (np.abs(yaw) < 0.02) & (np.abs(a_lat) < 0.3) & (v > 8.0)
    if mask.sum() < 50:
        return 0.0
    return float(np.median(delta[mask]))


def v4_predict(t, delta_road, v, bias, p):
    delta_c = delta_road - bias
    tau = 0.05
    dt = np.median(np.diff(t))
    alpha = dt / (tau + dt)
    delta_eff = np.empty_like(delta_c)
    delta_eff[0] = delta_c[0]
    for k in range(1, len(delta_c)):
        delta_eff[k] = delta_eff[k - 1] + alpha * (delta_c[k] - delta_eff[k - 1])
    scale = p.get("kus_scale", 1.0)
    Kus = scale * k_us(p)
    return (v * np.tan(delta_eff)) / (p["L"] + Kus * v * v)


def main():
    sse_agent = 0.0
    sse_base = 0.0
    n_tot = 0
    n_seg = 0

    for platform, _ in PLATFORM_GLOBS:
        platform_dir = SIM / platform
        p = ST_BY_PLATFORM[platform]
        for csv_path in sorted(platform_dir.rglob("sim.csv")):
            try:
                rows = np.loadtxt(csv_path, delimiter=",", skiprows=1)
            except Exception:
                continue
            if rows.ndim != 2 or rows.shape[0] < 2:
                continue
            t = rows[:, 0]
            delta_road = rows[:, 2]
            v = rows[:, 3]
            a_lat = rows[:, 5]
            yaw_meas = rows[:, 6]
            yaw_pred_base = rows[:, 14]

            bias = estimate_bias(t, delta_road, v, a_lat, yaw_meas)
            yp = v4_predict(t, delta_road, v, bias, p)

            mask = v > 2.0
            if not mask.any():
                n_seg += 1
                continue
            err_agent = (yp - yaw_meas)[mask]
            err_base = (yaw_pred_base - yaw_meas)[mask]
            sse_agent += float(np.sum(err_agent * err_agent))
            sse_base += float(np.sum(err_base * err_base))
            n_tot += int(mask.sum())
            n_seg += 1

    baseline_rmse_canonical = 0.014740020892723483
    baseline_rmse_recomputed = float(np.sqrt(sse_base / n_tot))
    agent_rmse = float(np.sqrt(sse_agent / n_tot))
    improvement_pct = (baseline_rmse_canonical - agent_rmse) / baseline_rmse_canonical * 100.0

    notes_parts = []
    if abs(baseline_rmse_recomputed - baseline_rmse_canonical) > 1e-6:
        notes_parts.append(
            f"baseline_rmse_recomputed ({baseline_rmse_recomputed:.12f}) deviates from canonical V0 ({baseline_rmse_canonical:.12f}) by > 1e-6"
        )
    notes_parts.append(
        "Reconstructed v4 (final ladder rung) from tools/score.py: per-segment bias subtraction + steady-state single-track with platform-tuned K_us (Mach-E 0.5x, F-150 3.0x) + first-order steering lag tau=0.05s; parameters hard-coded in agent's script, no external fit needed."
    )

    out = {
        "agent_id": "raw-agent-06",
        "status": "ok",
        "reason": None,
        "reconstruction_method": "imported-function",
        "reconstruction_summary": "Reimplemented v4_per_platform_kus from agent's tools/score.py: per-segment steering bias + first-order lag (tau=0.05s) on delta + steady-state single-track psi_dot = v*tan(delta_eff)/(L + scale*K_us*v^2) with K_us scales Mach-E 0.5x, F-150 3.0x.",
        "n_segments": n_seg,
        "n_samples_after_filter": n_tot,
        "baseline_rmse": baseline_rmse_canonical,
        "baseline_rmse_recomputed": baseline_rmse_recomputed,
        "agent_rmse": agent_rmse,
        "improvement_pct": improvement_pct,
        "notes": " | ".join(notes_parts),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
