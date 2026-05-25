"""Baseline + ablation analysis for KS lateral residuals on Ford CSVs.

Reads the pre-existing sim CSVs (read-only data dir), computes:

1. Baseline RMSE (ψ̇ in °/s, a_y in m/s²) per platform, correlation,
   and regime-conditioned residuals.
2. Three improvements re-applied analytically from the CSV columns
   (since we have measured v, measured δ_road, measured ψ̇, and measured a_y):
   - A1: yaw-rate bias correction (per-segment median residual).
   - A2: Steering-compliance/lag model (first-order lag on δ_road).
   - A3: Wheelbase recalibration (least-squares fit of effective L,
         constrained to within ±15% of canonical).
4. Ablation table (baseline → +A1 → +A1+A2 → +A1+A2+A3) per platform,
   and per individual improvement.

Outputs:
   out/baseline_per_segment.csv
   out/baseline_per_platform.csv
   out/regime_breakdown.csv
   out/ablation.csv
   out/recalibrated_wheelbase.csv
   out/residual_hist.png
   out/residual_vs_lat_g.png
"""

from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA_ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/data/sim/segments")
OUT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-C/modulo-2/out")
OUT.mkdir(parents=True, exist_ok=True)

PLATFORMS = ["FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]

# Canonical wheelbases (from parameters.py).
L_CANON = {
    "FORD_MUSTANG_MACH_E_MK1": 2.984,
    "FORD_F_150_LIGHTNING_MK1": 3.70,
}


def find_csvs(platform: str) -> list[Path]:
    return sorted((DATA_ROOT / platform).rglob("sim.csv"))


def rmse(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.asarray(x) ** 2)))


def rad_to_degs(x: np.ndarray) -> np.ndarray:
    return np.asarray(x) * 180.0 / np.pi


# ---- Predictors ---------------------------------------------------------

def predict_yaw_rate(v_mps, delta_road_rad, L):
    """KS yaw-rate from speed and road-wheel angle."""
    return (v_mps / L) * np.tan(delta_road_rad)


def lag_filter(x: np.ndarray, tau_s: float, dt_s: float) -> np.ndarray:
    """First-order lag: y[k] = a*y[k-1] + (1-a)*x[k] with a=exp(-dt/tau)."""
    if tau_s <= 0:
        return x.copy()
    a = float(np.exp(-dt_s / tau_s))
    y = np.empty_like(x)
    y[0] = x[0]
    for k in range(1, len(x)):
        y[k] = a * y[k - 1] + (1.0 - a) * x[k]
    return y


def fit_lag_tau(delta, v_mps, yaw_meas, L, dt, grid=None):
    """Fit a delta-lag tau by minimising RMSE of yaw residual."""
    if grid is None:
        grid = np.concatenate([[0.0], np.linspace(0.02, 0.40, 20)])
    best = (None, np.inf)
    for tau in grid:
        d_lagged = lag_filter(delta, float(tau), dt)
        pred = predict_yaw_rate(v_mps, d_lagged, L)
        r = rmse(yaw_meas - pred)
        if r < best[1]:
            best = (float(tau), r)
    return best


def fit_wheelbase(delta, v_mps, yaw_meas, L_canon, bounds=(0.85, 1.15)):
    """Least-squares scaling factor s s.t. L_eff = s * L_canon minimises
    RMSE of yaw_meas - (v/L_eff)*tan(delta). Equivalently, fit k = 1/L_eff
    by linear regression of yaw_meas on (v*tan(delta))."""
    x = v_mps * np.tan(delta)
    # only use samples with meaningful steering and speed
    m = (np.abs(delta) > np.deg2rad(0.5)) & (v_mps > 3.0)
    if m.sum() < 200:
        return L_canon, np.nan
    # k_opt = (x·y)/(x·x)
    k = float(np.dot(x[m], yaw_meas[m]) / np.dot(x[m], x[m]))
    L_eff = 1.0 / k if k > 0 else L_canon
    # constrain
    s = L_eff / L_canon
    s = float(np.clip(s, bounds[0], bounds[1]))
    return L_canon * s, s


# ---- Main ---------------------------------------------------------------

def regime_stats(df: pd.DataFrame, label: str) -> list[dict]:
    """Bucket residuals by speed, |delta|, and |a_y|."""
    rows = []
    res_deg = rad_to_degs(df["yaw_rate_resid_rads"].values)
    v = df["v_mps"].values
    d_abs = np.abs(df["delta_road_rad"].values)
    ay_abs = np.abs(df["a_lat_meas_mps2"].values)

    def bucket(name, mask, key):
        if mask.sum() < 20:
            return
        rows.append(dict(
            scope=label, regime=name, bucket=key,
            n=int(mask.sum()),
            rmse_yaw_degs=rmse(res_deg[mask]),
            mean_yaw_degs=float(np.mean(res_deg[mask])),
        ))

    # Speed bins
    for lo, hi in [(0, 5), (5, 15), (15, 25), (25, 50)]:
        bucket("speed_mps", (v >= lo) & (v < hi), f"{lo}-{hi}")
    # |delta_road| bins (deg)
    d_deg = np.degrees(d_abs)
    for lo, hi in [(0, 1), (1, 3), (3, 6), (6, 90)]:
        bucket("abs_delta_deg", (d_deg >= lo) & (d_deg < hi), f"{lo}-{hi}")
    # |a_y| bins
    for lo, hi in [(0, 1), (1, 2), (2, 4), (4, 20)]:
        bucket("abs_ay_mps2", (ay_abs >= lo) & (ay_abs < hi), f"{lo}-{hi}")
    return rows


def process():
    per_seg = []
    per_plat = []
    regime_rows = []
    ablation_rows = []
    recal_rows = []

    for plat in PLATFORMS:
        L = L_CANON[plat]
        csvs = find_csvs(plat)
        plat_frames = []
        for csvp in csvs:
            df = pd.read_csv(csvp)
            dt = float(df["t_s"].iloc[1] - df["t_s"].iloc[0])
            v = df["v_mps"].values
            d = df["delta_road_rad"].values
            yaw_m = df["yaw_rate_meas_rads"].values
            ay_m = df["a_lat_meas_mps2"].values

            # ---- Baseline (use pre-computed columns) ----
            base_yaw_res = df["yaw_rate_resid_rads"].values
            base_ay_res = df["a_y_resid_mps2"].values
            corr_yaw = float(np.corrcoef(df["yaw_rate_pred_rads"], yaw_m)[0, 1])
            corr_ay = float(np.corrcoef(df["a_y_pred_mps2"], ay_m)[0, 1])

            per_seg.append(dict(
                platform=plat,
                segment=str(csvp.relative_to(DATA_ROOT)),
                n=len(df),
                rmse_yaw_degs=rad_to_degs(rmse(base_yaw_res)),
                rmse_ay_mps2=rmse(base_ay_res),
                corr_yaw_pred_meas=corr_yaw,
                corr_ay_pred_meas=corr_ay,
                mean_yaw_res_degs=float(np.mean(rad_to_degs(base_yaw_res))),
                p95_abs_yaw_res_degs=float(np.percentile(np.abs(rad_to_degs(base_yaw_res)), 95)),
            ))

            df["__plat"] = plat
            df["__seg"] = str(csvp.relative_to(DATA_ROOT))
            plat_frames.append(df)

            # ---- Ablations (per segment) ----
            # A1: bias = median(meas - pred)
            bias = float(np.median(base_yaw_res))
            yaw_a1 = base_yaw_res - bias  # subtract bias from residual

            # A2: lag-filter delta then re-predict
            tau_opt, _ = fit_lag_tau(d, v, yaw_m, L, dt)
            d_lag = lag_filter(d, tau_opt, dt)
            pred_a2 = predict_yaw_rate(v, d_lag, L)
            yaw_a2_only = yaw_m - pred_a2
            # A1+A2
            yaw_a1a2 = yaw_a2_only - float(np.median(yaw_a2_only))

            # A3: wheelbase recalibration (using yaw_meas as truth)
            L_eff, scale = fit_wheelbase(d, v, yaw_m, L)
            pred_a3 = predict_yaw_rate(v, d, L_eff)
            yaw_a3_only = yaw_m - pred_a3
            # A1+A2+A3 (re-fit L on lagged delta)
            L_eff2, scale2 = fit_wheelbase(d_lag, v, yaw_m, L)
            pred_a1a2a3 = predict_yaw_rate(v, d_lag, L_eff2)
            yaw_a1a2a3 = yaw_m - pred_a1a2a3
            yaw_a1a2a3 = yaw_a1a2a3 - float(np.median(yaw_a1a2a3))

            recal_rows.append(dict(
                platform=plat,
                segment=str(csvp.relative_to(DATA_ROOT)),
                L_canonical_m=L,
                L_eff_baseline_delta_m=L_eff,
                scale_baseline=scale,
                L_eff_lagged_delta_m=L_eff2,
                scale_lagged=scale2,
                lag_tau_s=tau_opt,
                bias_rads=bias,
            ))

            def add_ab(name, res):
                ablation_rows.append(dict(
                    platform=plat,
                    segment=str(csvp.relative_to(DATA_ROOT)),
                    variant=name,
                    rmse_yaw_degs=rad_to_degs(rmse(res)),
                ))

            add_ab("baseline", base_yaw_res)
            add_ab("A1_bias", yaw_a1)
            add_ab("A2_lag", yaw_a2_only)
            add_ab("A3_wheelbase", yaw_a3_only)
            add_ab("A1+A2", yaw_a1a2)
            add_ab("A1+A2+A3", yaw_a1a2a3)

        # Platform aggregate (concatenate all segments)
        plat_df = pd.concat(plat_frames, ignore_index=True)
        agg_baseline = rad_to_degs(rmse(plat_df["yaw_rate_resid_rads"].values))
        agg_ay = rmse(plat_df["a_y_resid_mps2"].values)
        per_plat.append(dict(
            platform=plat,
            n_segments=len(plat_frames),
            n_rows=len(plat_df),
            rmse_yaw_degs=agg_baseline,
            rmse_ay_mps2=agg_ay,
            mean_yaw_res_degs=float(np.mean(rad_to_degs(plat_df["yaw_rate_resid_rads"]))),
            corr_yaw=float(np.corrcoef(plat_df["yaw_rate_pred_rads"], plat_df["yaw_rate_meas_rads"])[0, 1]),
            corr_ay=float(np.corrcoef(plat_df["a_y_pred_mps2"], plat_df["a_lat_meas_mps2"])[0, 1]),
        ))

        regime_rows.extend(regime_stats(plat_df, plat))

    # Write outputs
    pd.DataFrame(per_seg).to_csv(OUT / "baseline_per_segment.csv", index=False)
    pd.DataFrame(per_plat).to_csv(OUT / "baseline_per_platform.csv", index=False)
    pd.DataFrame(regime_rows).to_csv(OUT / "regime_breakdown.csv", index=False)
    pd.DataFrame(recal_rows).to_csv(OUT / "recalibrated_wheelbase.csv", index=False)

    # Aggregate ablation per platform
    abl = pd.DataFrame(ablation_rows)
    # weight each segment equally by averaging RMSEs across segments
    plat_abl = (abl.groupby(["platform", "variant"])["rmse_yaw_degs"]
                  .mean().reset_index())
    base_map = (plat_abl[plat_abl["variant"] == "baseline"]
                .set_index("platform")["rmse_yaw_degs"].to_dict())
    plat_abl["delta_abs_degs"] = plat_abl.apply(
        lambda r: r["rmse_yaw_degs"] - base_map[r["platform"]], axis=1)
    plat_abl["delta_rel_pct"] = plat_abl.apply(
        lambda r: 100.0 * r["delta_abs_degs"] / base_map[r["platform"]], axis=1)
    plat_abl.to_csv(OUT / "ablation.csv", index=False)
    abl.to_csv(OUT / "ablation_per_segment.csv", index=False)

    # ---- Plots ----
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), sharey=True)
    for ax, plat in zip(axes, PLATFORMS):
        frames = [pd.read_csv(c) for c in find_csvs(plat)]
        all_res = np.concatenate([rad_to_degs(f["yaw_rate_resid_rads"].values) for f in frames])
        ax.hist(all_res, bins=80, color="C0", alpha=0.8)
        ax.set_title(f"{plat}\nRMSE={rmse(all_res):.2f} °/s, mean={all_res.mean():+.2f}")
        ax.set_xlabel("yaw-rate residual (°/s)")
        ax.axvline(0, color="k", lw=0.5)
    axes[0].set_ylabel("count")
    fig.tight_layout()
    fig.savefig(OUT / "residual_hist.png", dpi=120)
    plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for ax, plat in zip(axes, PLATFORMS):
        frames = [pd.read_csv(c) for c in find_csvs(plat)]
        d = np.concatenate([f["a_lat_meas_mps2"].values for f in frames])
        r = np.concatenate([rad_to_degs(f["yaw_rate_resid_rads"].values) for f in frames])
        ax.scatter(d, r, s=2, alpha=0.3)
        ax.set_xlabel("measured a_y (m/s²)")
        ax.set_ylabel("yaw-rate residual (°/s)")
        ax.set_title(plat)
        ax.axhline(0, color="k", lw=0.5)
        ax.axvline(0, color="k", lw=0.5)
    fig.tight_layout()
    fig.savefig(OUT / "residual_vs_lat_g.png", dpi=120)
    plt.close(fig)

    # Print headline
    print("\n=== BASELINE per platform ===")
    print(pd.DataFrame(per_plat).to_string(index=False))
    print("\n=== ABLATION (mean RMSE °/s across segments) ===")
    print(plat_abl.to_string(index=False))
    print("\n=== RECAL ===")
    print(pd.DataFrame(recal_rows).to_string(index=False))


if __name__ == "__main__":
    process()
