"""Smoke test for load-segments. Runnable standalone: `python3 _smoke.py`.

Loads Mach-E segments from the project's `data/` tree and asserts that the
returned DataFrames have the expected shape, dtypes, and attrs.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# The skill resolves paths relative to CWD. Set CWD to the webinar-AI repo root
# so `data/sim/segments/...` resolves. We locate the repo by walking up from
# this file until we find a `data/` directory.
HERE = Path(__file__).resolve().parent

# Make `load.py` importable as a sibling module.
sys.path.insert(0, str(HERE))

# Walk up to find a directory containing data/sim/segments.
_cur = HERE
_repo_root = None
for _ in range(8):
    if (_cur / "data" / "sim" / "segments").is_dir():
        _repo_root = _cur
        break
    _cur = _cur.parent

if _repo_root is None:
    print("smoke FAILED: could not find a data/sim/segments directory above this skill")
    sys.exit(1)

os.chdir(_repo_root)

from load import load  # noqa: E402  (sys.path fixed above)


def main() -> int:
    platform = "FORD_MUSTANG_MACH_E_MK1"
    dfs = load(platform=platform)

    # 1. We got a reasonable batch back.
    assert isinstance(dfs, list), f"expected list, got {type(dfs)!r}"
    assert len(dfs) >= 5, f"expected at least 5 segments, got {len(dfs)}"

    # 2. Every df has the right platform attr.
    for df in dfs:
        assert df.attrs.get("platform") == platform, (
            f"bad platform attr: {df.attrs.get('platform')!r}"
        )
        for key in ("segment_path", "device", "route", "idx"):
            assert key in df.attrs and df.attrs[key], f"missing/empty attr: {key}"

    # 3. Critical columns present and float-typed.
    critical = ["t_s", "v_mps", "yaw_rate_meas_rads", "yaw_rate_pred_rads"]
    for df in dfs:
        for col in critical:
            assert col in df.columns, f"missing critical column {col!r}"
            assert df[col].dtype.kind == "f", (
                f"column {col!r} is dtype {df[col].dtype}, expected float"
            )

    # 4. No NaN in t_s or v_mps.
    for df in dfs:
        assert not df["t_s"].isna().any(), "NaN in t_s"
        assert not df["v_mps"].isna().any(), "NaN in v_mps"

    # Human-readable summary.
    total_rows = sum(len(df) for df in dfs)
    print(f"smoke OK: n_dfs={len(dfs)}, total_rows={total_rows}")
    print(f"  sample df.attrs: {dict(dfs[0].attrs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
