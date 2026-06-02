"""k-fold route-grouped CV wrapper around `score()`, plus test-split refusal.

See SKILL.md § "m4 addendum" for the contract. This is the SKELETON — extend
the fold partitioning to use make-train-dev-split's route-grouped output.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any

import numpy as np

# The skill dir is hyphenated (`score-model/`), so `from .score import ...`
# fails when this file is loaded by importlib.spec_from_file_location with
# no package set. Load score.py from disk instead.
_SCORE_PATH = Path(__file__).resolve().parent / "score.py"
if str(_SCORE_PATH.parent) not in sys.path:
    sys.path.insert(0, str(_SCORE_PATH.parent))
from score import (  # type: ignore  # noqa: E402
    TEST_SPLIT_MARKER_PARTS,  # noqa: F401 — re-exported for callers
    TestSplitDeniedError,     # noqa: F401 — re-exported for callers
    _assert_not_test,
    score,
)


def score_cv(predict_fn, segment_paths=None, k: int = 5, *, final: bool = False, **kwargs) -> dict[str, Any]:
    """k-fold route-grouped CV. Returns pooled mean ± std plus the per-fold raw."""
    _assert_not_test(segment_paths, final=final)
    paths = list(segment_paths or _default_dev_segments())
    folds = _route_grouped_folds(paths, k=k)

    fold_results = []
    for fold_idx, fold_paths in enumerate(folds):
        r = score(predict_fn, segment_paths=fold_paths, **kwargs)
        fold_results.append({
            "fold": fold_idx,
            "yaw_rate_rmse": r["yaw_rate_rmse"],
            "cte_rmse": r["cte_rmse"],
            "n_segments": r["n_segments"],
        })

    yaws = np.array([f["yaw_rate_rmse"] for f in fold_results])
    ctes = np.array([f["cte_rmse"] for f in fold_results])
    pooled = {
        "yaw_rmse": float(yaws.mean()),
        "yaw_std":  float(yaws.std(ddof=1) if len(yaws) > 1 else 0.0),
        "cte_rmse": float(ctes.mean()),
        "cte_std":  float(ctes.std(ddof=1) if len(ctes) > 1 else 0.0),
    }
    return {"pooled": pooled, "folds": fold_results}


def _default_dev_segments():
    """Return all dev segment paths. Replace with the project's split convention.
    SKELETON — extend to actually filter out test segments."""
    template_root = Path(__file__).resolve().parents[2]
    return sorted((template_root / "data" / "sim" / "segments").rglob("sim.csv"))


def _route_grouped_folds(paths, k: int = 5):
    """Partition paths into k folds, never splitting a route across folds.

    SKELETON — replace with the make-train-dev-split route-grouped partitioner.
    """
    by_route: dict[str, list] = {}
    for p in paths:
        # <PLATFORM>/<DEVICE>/<ROUTE>/<IDX>/sim.csv — route is parents[1].
        route = str(p.parents[1])
        by_route.setdefault(route, []).append(p)
    routes = sorted(by_route)
    folds = [[] for _ in range(k)]
    for i, r in enumerate(routes):
        folds[i % k].extend(by_route[r])
    return folds
