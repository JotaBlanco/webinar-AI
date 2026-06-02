"""Refit on ALL sim segments for the final shipping coefficients.

Same feature set as fit_corrections.py. We previously verified on dev that the
ridge head generalises (route-grouped split). Now we use everything we've got
so the shipped coefficients are the best estimate.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fit_corrections import (
    list_segments,
    fit_platform,
    fit_bias_only,
    PLATFORMS_WITH_TRUTH,
    FEATURE_NAMES,
)

ROOT = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-4.v1/agent-10")


def main():
    out = {"platforms": {}, "feature_names": FEATURE_NAMES, "v_center": 15.0, "l2": 10.0}
    for platform in PLATFORMS_WITH_TRUTH:
        paths = list_segments(platform)
        bias = fit_bias_only(paths)
        ridge = fit_platform(paths, l2=10.0)
        out["platforms"][platform] = {"bias_only": bias, "ridge": ridge}
        print(f"{platform}: n_seg={len(paths)} bias={bias:+.5f} ridge_train_rmse={ridge['train_rmse_residual']:.5f} naive={ridge['naive_rmse_residual']:.5f}")
    out_path = ROOT / "final-model" / "coefficients.json"
    with out_path.open("w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
