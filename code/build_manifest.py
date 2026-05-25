#!/usr/bin/env python3
"""Build manifest.json for a downloaded platform under KB003/data/segments/<PLATFORM>/.

Manifest schema:
{
  "platform": "TESLA_MODEL_3",
  "source": {"dataset": "commaai/commaCarSegments", "ref": "main"},
  "generated_at": "<ISO8601>",
  "totals": {"devices": N, "routes": M, "segments": K, "bytes": B, "duration_minutes_approx": K*1},
  "devices": {
      "<device_id>": {
          "routes": {
              "<route_id>": {
                  "segments": [
                      {"idx": "<int_as_str>", "bytes": B, "path": "segments/.../rlog.zst"}
                  ],
                  "segment_count": int,
                  "duration_minutes_approx": int
              }
          },
          "route_count": int,
          "segment_count": int
      }
  }
}
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PLATFORM = sys.argv[1] if len(sys.argv) > 1 else "TESLA_MODEL_3"
ROOT = Path(__file__).resolve().parent.parent / "data" / "raw"
PLAT_DIR = ROOT / "segments" / PLATFORM


_DECODER_DEFAULT = "opendbc per-vehicle profile"
_DECODER_BY_PLATFORM = {
    "TESLA_MODEL_3": "opendbc per-vehicle profile (TESLA_MODEL_3 reverse-engineered)",
    "FORD_MUSTANG_MACH_E_MK1": "opendbc per-vehicle profile (Ford, officially supported port; carstate.py populates ret.yawRate from Yaw_Data_FD1.VehYaw_W_Actl)",
    "FORD_F_150_LIGHTNING_MK1": "opendbc per-vehicle profile (Ford, officially supported port; carstate.py populates ret.yawRate from Yaw_Data_FD1.VehYaw_W_Actl)",
}

_RATES_NOTE_DEFAULT = "Per-signal CAN cadence varies by OEM. The 100 Hz figure is the rlog envelope; verify physical rates against a sample rlog before depending on them."
_RATES_NOTE_BY_PLATFORM = {
    "TESLA_MODEL_3": "Tesla CAN rates are reverse-engineered. Per-signal cadence varies and is not codified in openpilot's TESLA carstate.py; verify against a sample rlog.",
    "FORD_MUSTANG_MACH_E_MK1": "Ford CAN: yawRate populated directly from CAN (Yaw_Data_FD1.VehYaw_W_Actl, rad/s). Lateral accel (VehLatComp_A_Actl) and roll rate are present in ford_lincoln_base_pt.dbc but not currently piped into cereal carState — small carstate.py patch surfaces them.",
    "FORD_F_150_LIGHTNING_MK1": "Ford CAN: yawRate populated directly from CAN (Yaw_Data_FD1.VehYaw_W_Actl, rad/s). Lateral accel (VehLatComp_A_Actl) and roll rate are present in ford_lincoln_base_pt.dbc but not currently piped into cereal carState — small carstate.py patch surfaces them.",
}


def main():
    if not PLAT_DIR.exists():
        sys.exit(f"Missing {PLAT_DIR}")

    devices = {}
    total_bytes = 0
    total_segments = 0
    total_routes = 0

    for device_dir in sorted(p for p in PLAT_DIR.iterdir() if p.is_dir()):
        device_id = device_dir.name
        routes = {}
        d_segs = 0
        for route_dir in sorted(p for p in device_dir.iterdir() if p.is_dir()):
            route_id = route_dir.name
            segs = []
            for idx_dir in sorted(
                (p for p in route_dir.iterdir() if p.is_dir()),
                key=lambda p: int(p.name) if p.name.isdigit() else p.name,
            ):
                rlog = idx_dir / "rlog.zst"
                if not rlog.exists():
                    continue
                size = rlog.stat().st_size
                rel = rlog.relative_to(ROOT).as_posix()
                segs.append({"idx": idx_dir.name, "bytes": size, "path": rel})
                total_bytes += size
            if not segs:
                continue
            routes[route_id] = {
                "segments": segs,
                "segment_count": len(segs),
                "duration_minutes_approx": len(segs),  # 1 segment = ~1 minute
            }
            d_segs += len(segs)
            total_routes += 1
        if not routes:
            continue
        devices[device_id] = {
            "routes": routes,
            "route_count": len(routes),
            "segment_count": d_segs,
        }
        total_segments += d_segs

    manifest = {
        "platform": PLATFORM,
        "source": {
            "dataset": "commaai/commaCarSegments",
            "ref": "main",
            "license": "MIT",
            "homepage": "https://huggingface.co/datasets/commaai/commaCarSegments",
            "segment_url_pattern": "https://huggingface.co/datasets/commaai/commaCarSegments/resolve/main/segments/<device>/<route>/<idx>/rlog.zst",
        },
        "format": {
            "file": "rlog.zst",
            "description": "zstandard-compressed openpilot cereal log",
            "reader": "openpilot.tools.lib.logreader.LogReader",
            "decoder": _DECODER_BY_PLATFORM.get(PLATFORM, _DECODER_DEFAULT),
        },
        "rates_hint": {
            "rlog_envelope_hz": 100,
            "note": _RATES_NOTE_BY_PLATFORM.get(PLATFORM, _RATES_NOTE_DEFAULT),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "totals": {
            "devices": len(devices),
            "routes": total_routes,
            "segments": total_segments,
            "bytes": total_bytes,
            "gigabytes": round(total_bytes / 1024**3, 3),
            "duration_minutes_approx": total_segments,
            "duration_hours_approx": round(total_segments / 60, 2),
        },
        "devices": devices,
    }

    out = PLAT_DIR / "manifest.json"
    with open(out, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"Wrote {out}")
    print(json.dumps(manifest["totals"], indent=2))


if __name__ == "__main__":
    main()
