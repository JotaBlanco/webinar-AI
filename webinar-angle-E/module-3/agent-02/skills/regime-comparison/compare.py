"""compare.py — helpers for regime-comparison skill."""
from __future__ import annotations

import numpy as np
import pandas as pd

REGIMES = ("straight", "steady", "transient")


def _rmse(arr):
    a = np.asarray(arr, dtype=float)
    a = a[np.isfinite(a)]
    return float("nan") if a.size == 0 else float(np.sqrt(np.mean(a ** 2)))


def contrast(df: pd.DataFrame, variant_residuals: dict[str, np.ndarray], baseline_name: str = "V0"):
    """Build a per-regime contrast table relative to the baseline.

    `variant_residuals` is a dict like {'V0': array, 'V1': array, ...}.
    Returns a pandas DataFrame with columns [variant, delta_straight, delta_steady, delta_transient, dominant_regime].
    """
    if baseline_name not in variant_residuals:
        raise ValueError(f"missing baseline {baseline_name!r}")
    if "regime" not in df.columns:
        raise ValueError("df needs a `regime` column")
    reg = df["regime"].to_numpy()

    base = {r: _rmse(variant_residuals[baseline_name][reg == r]) for r in REGIMES}

    rows = []
    for name, resid in variant_residuals.items():
        per = {r: _rmse(resid[reg == r]) for r in REGIMES}
        deltas = {r: per[r] - base[r] for r in REGIMES}
        # Pick regime with largest |delta| (ignoring NaN).
        finite = {r: d for r, d in deltas.items() if np.isfinite(d)}
        dom = max(finite.items(), key=lambda kv: abs(kv[1]))[0] if finite else "—"
        rows.append({
            "variant": name,
            "delta_straight": deltas["straight"],
            "delta_steady": deltas["steady"],
            "delta_transient": deltas["transient"],
            "dominant_regime": dom,
        })
    return pd.DataFrame(rows)
