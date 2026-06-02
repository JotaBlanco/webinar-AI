"""Slice residuals by physics regime to recommend which of M1-M5 to try.

See SKILL.md for the regime definitions and routing logic.

The slicing uses only allowlist columns plus the predictor's own output —
no truth used for regime classification. RMSE within each regime is then
computed against the per-platform truth column from `score-model`'s
PLATFORM_SCHEMA.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

SKILL_DIR = Path(__file__).resolve().parent
TPL = SKILL_DIR.parents[1]
sys.path.insert(0, str(TPL))
sys.path.insert(0, str(TPL / "skills" / "score-model"))
from score import PLATFORM_SCHEMA, DEFAULT_SCHEMA  # noqa: E402

V_BAND_EDGES = [0.0, 8.0, 16.0, 24.0, 1e9]
V_BAND_NAMES = ["v<8", "v∈[8,16)", "v∈[16,24)", "v≥24"]


def _regime_masks(sim_df: pd.DataFrame, yr_pred: np.ndarray, platform: str) -> dict[str, np.ndarray]:
    n = len(sim_df)
    t = sim_df["t_s"].to_numpy()
    delta = sim_df["delta_road_rad"].to_numpy()
    v = sim_df["v_mps"].to_numpy()
    dt = np.diff(t, prepend=t[0])
    dt[dt <= 0] = 1e-3
    ddelta = np.abs(np.diff(delta, prepend=delta[0]) / dt)

    a_lat_proxy = np.abs(v * yr_pred)

    a_long = sim_df.get("a_long_mps2", pd.Series(np.zeros(n))).to_numpy()
    if "brake_pressed" in sim_df.columns:
        brake = sim_df["brake_pressed"].to_numpy().astype(float)
    else:
        brake = (a_long < -0.5).astype(float)

    masks = {
        "transient_steering":   ddelta > 0.05,
        "high_lat_accel":       a_lat_proxy > 4.0,
        "heavy_load_transfer":  (platform == "FORD_F_150_LIGHTNING_MK1") & (a_lat_proxy > 2.0),
        "brake_or_accel":       (brake > 0.5) | (np.abs(a_long) > 1.5),
    }
    return masks


def _v_band_rmse(v: np.ndarray, resid: np.ndarray) -> dict[str, float]:
    out = {}
    for i, name in enumerate(V_BAND_NAMES):
        lo, hi = V_BAND_EDGES[i], V_BAND_EDGES[i + 1]
        m = (v >= lo) & (v < hi)
        if m.sum() < 10:
            continue
        out[name] = float(np.sqrt(np.mean(resid[m] ** 2)))
    return out


def diagnose(predict_fn, segment_paths=None, platform_filter: str | None = None) -> dict:
    if segment_paths is None:
        sys.path.insert(0, str(TPL / "_shared"))
        from frozen_split import dev_paths
        segment_paths = dev_paths()

    accum: dict[str, dict[str, dict[str, list[float]]]] = {}
    v_band_accum: dict[str, dict[str, list[float]]] = {}
    pooled_n_sq = 0.0
    pooled_n = 0
    n_failed = 0
    n_ok = 0

    for path in segment_paths:
        platform = path.parts[-5]
        if platform_filter and platform != platform_filter:
            continue
        schema = PLATFORM_SCHEMA.get(platform, DEFAULT_SCHEMA)
        truth_col = schema["truth_col"]
        try:
            sim_df = pd.read_csv(path)
            if truth_col not in sim_df.columns:
                n_failed += 1
                continue
            # Mirror score-model's PLATFORM_SCHEMA aliasing so predict() sees
            # `yaw_rate_pred_rads` even on platforms whose V0 baseline column
            # is named differently (e.g. Tesla's `psi_dot_rads`).
            baseline_col = schema.get("baseline_col", "yaw_rate_pred_rads")
            if baseline_col != "yaw_rate_pred_rads" and "yaw_rate_pred_rads" not in sim_df.columns:
                sim_df["yaw_rate_pred_rads"] = sim_df[baseline_col]
            pred_df = predict_fn(sim_df, platform)
            yr_pred = pred_df["yaw_rate_pred_rads"].to_numpy()
            yr_truth = sim_df[truth_col].to_numpy()
        except Exception:
            n_failed += 1
            continue

        resid = yr_pred - yr_truth
        v = sim_df["v_mps"].to_numpy()
        mask_speed = v >= 2.0
        resid_v = resid[mask_speed]
        if len(resid_v) == 0:
            continue
        pooled_n_sq += float(np.sum(resid_v ** 2))
        pooled_n += int(mask_speed.sum())
        n_ok += 1

        masks = _regime_masks(sim_df, yr_pred, platform)
        plat_acc = accum.setdefault(platform, {})
        for name, m in masks.items():
            m_clean = m & mask_speed
            if m_clean.sum() == 0:
                continue
            entry = plat_acc.setdefault(name, {"sum_sq": 0.0, "n": 0})
            entry["sum_sq"] += float(np.sum(resid[m_clean] ** 2))
            entry["n"] += int(m_clean.sum())

        # Speed-banded RMSE for the phase-lag detector.
        vb = v_band_accum.setdefault(platform, {})
        for band, rmse in _v_band_rmse(v, resid).items():
            entry = vb.setdefault(band, {"sum_sq": 0.0, "n": 0})
            entry["sum_sq"] += rmse * rmse * int(mask_speed.sum())  # approximate
            entry["n"] += 1

    # Finalise per-regime RMSE + energy share.
    regime_rmse: dict[str, dict[str, dict]] = {}
    for platform, regs in accum.items():
        regime_rmse[platform] = {}
        plat_pooled = sum(r["sum_sq"] for r in regs.values()) or 1.0
        for name, entry in regs.items():
            rmse = float(np.sqrt(entry["sum_sq"] / max(entry["n"], 1)))
            share = float(entry["sum_sq"]) / plat_pooled
            regime_rmse[platform][name] = {
                "yaw_rmse": rmse,
                "n_rows": entry["n"],
                "energy_share": share,
            }

    # Phase-lag detection: variance across v bands.
    phase_lag_signal: dict[str, float] = {}
    for platform, vb in v_band_accum.items():
        if len(vb) < 2:
            continue
        rmses = [float(np.sqrt(e["sum_sq"] / e["n"])) for e in vb.values() if e["n"] > 0]
        if len(rmses) < 2 or min(rmses) == 0:
            continue
        ratio = max(rmses) / min(rmses)
        if ratio > 1.5:
            phase_lag_signal[platform] = ratio

    # Aggregate model routing — sum energy_share by mapped model across platforms.
    REGIME_TO_MODEL = {
        "transient_steering":  "m1-linear-dynamic-st",
        "high_lat_accel":      "m2-fiala-tire-st",
        "heavy_load_transfer": "m3-double-track-load-transfer",
        "brake_or_accel":      "m5-friction-circle",
    }
    model_scores: dict[str, dict] = {}
    for platform, regs in regime_rmse.items():
        for regime, stats in regs.items():
            model = REGIME_TO_MODEL.get(regime)
            if model is None:
                continue
            ms = model_scores.setdefault(model, {"score": 0.0, "evidence": []})
            ms["score"] += stats["energy_share"]
            ms["evidence"].append(
                f"{platform}: {regime} carries {stats['energy_share']*100:.0f}% of platform residual ({stats['n_rows']} rows)"
            )
    if phase_lag_signal:
        m4 = model_scores.setdefault("m4-relaxation-length", {"score": 0.0, "evidence": []})
        for plat, ratio in phase_lag_signal.items():
            m4["score"] += 0.2 * (ratio - 1.0)
            m4["evidence"].append(
                f"{plat}: residual RMSE varies {ratio:.1f}× across speed bands — speed-dependent phase lag"
            )

    ranked = sorted(model_scores.items(), key=lambda kv: -kv[1]["score"])
    routing = [
        {
            "model": model,
            "score": entry["score"],
            "why": "; ".join(entry["evidence"][:3]),
        }
        for model, entry in ranked
    ]

    pooled_rmse = float(np.sqrt(pooled_n_sq / max(pooled_n, 1)))

    return {
        "regime_rmse": regime_rmse,
        "phase_lag_signal": phase_lag_signal,
        "model_routing": routing,
        "pooled_yaw_rmse": pooled_rmse,
        "n_segments": n_ok,
        "n_failed": n_failed,
    }


def format_summary(result: dict) -> str:
    lines = [
        "# diagnose-by-physics-regime",
        "",
        f"- pooled yaw RMSE: **{result['pooled_yaw_rmse']:.5f} rad/s** "
        f"(n_segments={result['n_segments']}, failed={result['n_failed']})",
        "",
        "## Recommended models (ranked by residual-energy share)",
        "",
    ]
    for rec in result["model_routing"][:5]:
        lines.append(f"### `{rec['model']}` — score {rec['score']:.2f}")
        for ev in rec["why"].split("; "):
            lines.append(f"- {ev}")
        lines.append("")

    lines.append("## Per-platform regime breakdown")
    for platform, regs in result["regime_rmse"].items():
        lines.append(f"\n### {platform}")
        lines.append("| regime | yaw RMSE | n_rows | energy share |")
        lines.append("|---|---:|---:|---:|")
        for name, stats in sorted(regs.items(), key=lambda kv: -kv[1]["energy_share"]):
            lines.append(
                f"| `{name}` | {stats['yaw_rmse']:.5f} | {stats['n_rows']} | {stats['energy_share']*100:.0f}% |"
            )
    if result.get("phase_lag_signal"):
        lines.append("\n## Speed-banded residual ratio (M4 detector)")
        for plat, ratio in result["phase_lag_signal"].items():
            lines.append(f"- {plat}: RMSE varies {ratio:.2f}× across speed bands")
    return "\n".join(lines)


if __name__ == "__main__":
    # Quick smoke against V0 baseline.
    import argparse
    import importlib.util

    p = argparse.ArgumentParser()
    p.add_argument("--predict-module", default=None,
                   help="Optional path/to/predict.py to import.")
    args = p.parse_args()

    if args.predict_module:
        spec = importlib.util.spec_from_file_location("user_predict", args.predict_module)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        pf = mod.predict
    else:
        # Identity = score V0 directly.
        def pf(sim_df, platform):
            return sim_df[["yaw_rate_pred_rads"]].copy()

    result = diagnose(pf)
    print(format_summary(result))
