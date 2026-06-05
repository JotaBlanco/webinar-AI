#!/usr/bin/env python3
"""Discovery + suitability view for commaCarSegments platforms.

Default output: a ranked list of platforms suitable for the lateral-fidelity
challenge (yaw-rate + lateral-G truth channels), with segment counts, size
estimates, and a column showing what's already downloaded locally so you can
size a new fetch against the existing dataset.

Run this BEFORE fetch_platform.py. Discuss the output with the user, agree on
which platform(s) and how much to fetch, then invoke the downloader.

Usage:
    python recommend.py                       # default — lateral-suitable, ranked, with local comparison
    python recommend.py --all                 # every platform, no suitability filter
    python recommend.py --by-oem              # group by OEM family
    python recommend.py --local               # only show what's already downloaded
    python recommend.py --min-segments 50     # filter tiny platforms (default 100)
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

DB_PATH = Path("/tmp/ccs_database.json")


def repo_root_from_skill() -> Path:
    return Path(__file__).resolve().parents[3]


def load_data_paths(repo_root: Path):
    cfg = repo_root / "webinar-meta" / "data-paths.json"
    if not cfg.exists():
        return {"data_root": "data", "val_data_root": "data/val-data"}
    return json.loads(cfg.read_text())


# Lateral-fidelity suitability (decoded yaw-rate + lateral-G availability).
# Source: F1/KB002/public-data-sources/commacarsegments-per-oem-signals.md.
# Keyed on the OEM prefix (first underscore-separated token of platform name).
# verdict:
#   "yes"          first-class — yawRate already populated by openpilot's carstate.py
#   "yes-patch"    signals ship in the DBC; needs a ~10 LOC carstate.py patch to surface
#   "yes-partial"  decodable but newer/less proven or partial
#   "no"           not in shipped DBC — would need chassis-bus reverse engineering
LATERAL_VERDICT = {
    "FORD":       ("yes",         "first-class — yawRate populated from Yaw_Data_FD1.VehYaw_W_Actl. Lat-G one-line DBC patch."),
    "HYUNDAI":    ("yes-patch",   "ESP12 ships YAW_RATE + LAT_ACCEL on hyundai_kia_generic.dbc; small carstate.py patch."),
    "KIA":        ("yes-patch",   "Same DBC family as HYUNDAI; patch surfaces same signals."),
    "GENESIS":    ("yes-patch",   "Same DBC family as HYUNDAI; patch surfaces same signals."),
    "VOLKSWAGEN": ("yes-patch",   "MQB ESP_02 ships ESP_Gierrate + ESP_Querbeschleunigung; ~10 LOC carstate.py patch."),
    "AUDI":       ("yes-patch",   "VW MQB stablemate; verify model is on vw_mqb.dbc."),
    "SEAT":       ("yes-patch",   "VW MQB stablemate; verify model is on vw_mqb.dbc."),
    "SKODA":      ("yes-patch",   "VW MQB stablemate; verify model is on vw_mqb.dbc."),
    "RIVIAN":     ("yes-partial", "RCM_IMU_Yaw decodable; lat-G partial; port newer/less proven."),
    # No decoded yaw rate in shipped DBCs:
    "TESLA":      ("no",          "Party DBC ships only ESP_yawRateQF quality bit; IMU msg not reverse-engineered."),
    "TOYOTA":     ("no",          "No IMU in toyota_*_generated DBCs; chassis-bus reverse engineering required."),
    "LEXUS":      ("no",          "Toyota family — same DBC blocker."),
    "HONDA":      ("no",          "No IMU in honda_*_can_generated DBCs."),
    "ACURA":      ("no",          "Honda family — same blocker."),
    "GM":         ("no",          "No IMU in gm_global_a_powertrain_generated."),
    "CHEVROLET":  ("no",          "GM family — same blocker."),
    "CADILLAC":   ("no",          "GM family — same blocker."),
    "BUICK":      ("no",          "GM family — same blocker."),
    "GMC":        ("no",          "GM family — same blocker."),
    "SUBARU":     ("no",          "No IMU in subaru_global_2017_generated."),
    "MAZDA":      ("no",          "No IMU in mazda_2017."),
    "NISSAN":     ("no",          "No IMU in nissan_leaf_2018_generated."),
    "CHRYSLER":   ("no",          "No IMU in shipped Chrysler/Pacifica DBCs."),
    "RAM":        ("no",          "Chrysler family — same blocker."),
    "JEEP":       ("no",          "Chrysler family — same blocker."),
    "DODGE":      ("no",          "Chrysler family — same blocker."),
}
VERDICT_RANK = {"yes": 0, "yes-patch": 1, "yes-partial": 2, "no": 3, "unknown": 4}

# MB/segment observed from actual downloads. Used for size estimates.
BYTES_PER_SEG_MB = {
    "TESLA":    1.74,
    "FORD":     2.66,
    "HYUNDAI":  3.68,
    "KIA":      3.68,
    "GENESIS":  3.68,
}
DEFAULT_MB_PER_SEG = 2.5


def oem_of(platform: str) -> str:
    return platform.split("_", 1)[0].upper()


def verdict_for(platform: str):
    return LATERAL_VERDICT.get(oem_of(platform), ("unknown", "no signal-coverage data for this OEM."))


def estimate_mb(platform: str, n_segments: int) -> float:
    per = BYTES_PER_SEG_MB.get(oem_of(platform), DEFAULT_MB_PER_SEG)
    return n_segments * per


def load_db():
    if not DB_PATH.exists():
        sys.exit(f"Missing {DB_PATH}. Run: python build_ccs_database.py")
    return json.loads(DB_PATH.read_text())


def gather_local(repo_root: Path, paths: dict):
    """Return {platform: {"train_segs": n, "val_segs": n, "mb": total}}."""
    out: dict[str, dict] = defaultdict(lambda: {"train_segs": 0, "val_segs": 0, "mb": 0.0})
    for label, root_key in [("train_segs", "data_root"), ("val_segs", "val_data_root")]:
        plat_root = repo_root / paths[root_key] / "raw" / "segments"
        if not plat_root.exists():
            continue
        for plat_dir in plat_root.iterdir():
            if not plat_dir.is_dir():
                continue
            n = 0
            b = 0
            for rlog in plat_dir.rglob("rlog.zst"):
                n += 1
                b += rlog.stat().st_size
            out[plat_dir.name][label] += n
            out[plat_dir.name]["mb"] += b / 1024 / 1024
    return out


def print_table(rows, headers):
    if not rows:
        print("  (none)")
        return
    widths = [max(len(str(r[i])) for r in [headers] + rows) for i in range(len(headers))]
    fmt = "  " + "  ".join(f"{{:<{w}}}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*["-" * w for w in widths]))
    for r in rows:
        print(fmt.format(*r))


def render_default(db, local, min_segments):
    print(f"# commaCarSegments — lateral-fidelity suitability\n")
    print(f"  Source DB: {DB_PATH}  ({len(db)} platforms, "
          f"{sum(len(v) for v in db.values())} segments)")
    print(f"  Filter: min {min_segments} segments (use --min-segments / --all to widen)\n")

    rows_first_class = []
    rows_patch = []
    rows_partial = []
    rows_no_or_unknown = []

    for plat, segs in db.items():
        if len(segs) < min_segments:
            continue
        verdict, _note = verdict_for(plat)
        mb = estimate_mb(plat, len(segs))
        loc = local.get(plat, {})
        local_str = ""
        if loc:
            t = loc.get("train_segs", 0)
            v = loc.get("val_segs", 0)
            local_str = f"✓ {t}+{v}"
        row = (plat, oem_of(plat), len(segs), f"{mb/1024:.1f} GB", local_str)
        if verdict == "yes":
            rows_first_class.append(row)
        elif verdict == "yes-patch":
            rows_patch.append(row)
        elif verdict == "yes-partial":
            rows_partial.append(row)
        else:
            rows_no_or_unknown.append(row)

    for bucket in (rows_first_class, rows_patch, rows_partial, rows_no_or_unknown):
        bucket.sort(key=lambda r: -r[2])

    headers = ("Platform", "OEM", "Segments", "Size (est.)", "Local (train+val)")

    print("## yes — first-class lateral truth (no patch needed)\n")
    print_table(rows_first_class, headers)
    print()

    print("## yes-patch — yaw-rate in shipped DBC, ~10 LOC carstate.py patch to surface\n")
    print_table(rows_patch, headers)
    print()

    if rows_partial:
        print("## yes-partial — decodable but newer/less proven\n")
        print_table(rows_partial, headers)
        print()

    print(f"## no decoded yaw-rate ({len(rows_no_or_unknown)} platforms hidden)\n")
    print("  These ship DBCs without IMU signals — would need chassis-bus reverse engineering.")
    print("  Use --all to list them.\n")

    print_local_summary(local)
    print("\nNext step:")
    print("  1. Pick one or more platforms from the lists above.")
    print("  2. Decide volume — compare against your existing local totals.")
    print("  3. Run: python fetch_platform.py <PLATFORM> [--val-split --train N --val M]")


def render_all(db, local, min_segments):
    print(f"# commaCarSegments — ALL platforms (>= {min_segments} segments)\n")
    rows = []
    for plat, segs in db.items():
        if len(segs) < min_segments:
            continue
        verdict, _ = verdict_for(plat)
        mb = estimate_mb(plat, len(segs))
        loc = local.get(plat, {})
        local_str = ""
        if loc:
            local_str = f"✓ {loc.get('train_segs',0)}+{loc.get('val_segs',0)}"
        rows.append((plat, oem_of(plat), len(segs), f"{mb/1024:.1f} GB", verdict, local_str))
    rows.sort(key=lambda r: (VERDICT_RANK[r[4]], -r[2]))
    print_table(rows, ("Platform", "OEM", "Segments", "Size (est.)", "Lateral?", "Local (train+val)"))
    print()
    print_local_summary(local)


def render_by_oem(db, local, min_segments):
    print(f"# commaCarSegments — grouped by OEM\n")
    by_oem = defaultdict(list)
    for plat, segs in db.items():
        if len(segs) < min_segments:
            continue
        by_oem[oem_of(plat)].append((plat, len(segs)))

    for oem in sorted(by_oem):
        verdict, note = LATERAL_VERDICT.get(oem, ("unknown", "no data"))
        entries = sorted(by_oem[oem], key=lambda x: -x[1])
        total = sum(c for _, c in entries)
        marker = {"yes": "✅", "yes-patch": "⚠️", "yes-partial": "⚠️", "no": "❌", "unknown": "?"}[verdict]
        print(f"== {marker} {oem} — lateral {verdict} ({total} segs across {len(entries)} platforms) ==")
        print(f"   {note}")
        for plat, n in entries[:6]:
            local_str = ""
            if plat in local:
                t = local[plat].get("train_segs", 0); v = local[plat].get("val_segs", 0)
                local_str = f"  ← local {t}+{v}"
            print(f"     {plat:50s} {n:>5d} segs{local_str}")
        if len(entries) > 6:
            print(f"     ... and {len(entries) - 6} more")
        print()

    print_local_summary(local)


def print_local_summary(local):
    if not local:
        print("Local dataset: (empty — nothing downloaded yet)")
        return
    print("## Currently downloaded locally\n")
    rows = []
    total_segs = total_mb = 0
    for plat, info in sorted(local.items()):
        t = info.get("train_segs", 0); v = info.get("val_segs", 0); mb = info.get("mb", 0)
        verdict, _ = verdict_for(plat)
        rows.append((plat, oem_of(plat), t, v, f"{mb:.0f} MB", verdict))
        total_segs += t + v; total_mb += mb
    print_table(rows, ("Platform", "OEM", "Train", "Val", "Disk", "Lateral?"))
    print(f"\n  Total: {total_segs} segments, {total_mb/1024:.2f} GB across {len(local)} platforms")


def render_local_only(local):
    print(f"# Local dataset (from {DB_PATH.name})\n")
    print_local_summary(local)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true", help="Include platforms with no decoded yaw rate.")
    ap.add_argument("--by-oem", action="store_true", help="Group by OEM family.")
    ap.add_argument("--local", action="store_true", help="Only show what's downloaded locally.")
    ap.add_argument("--min-segments", type=int, default=100,
                    help="Hide platforms below this segment count (default 100).")
    args = ap.parse_args()

    repo_root = repo_root_from_skill()
    paths = load_data_paths(repo_root)
    local = gather_local(repo_root, paths)

    if args.local:
        render_local_only(local)
        return

    db = load_db()

    if args.by_oem:
        render_by_oem(db, local, args.min_segments)
    elif args.all:
        render_all(db, local, args.min_segments)
    else:
        render_default(db, local, args.min_segments)


if __name__ == "__main__":
    main()
