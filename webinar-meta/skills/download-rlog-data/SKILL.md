---
name: download-rlog-data
description: Discover, select, and download raw CAN-bus rlog segments for a vehicle platform from comma.ai's commaCarSegments dataset. ALWAYS runs the discovery step first (recommend.py) — surfaces what's available, whether each platform is suitable for the lateral-fidelity challenge (decoded yaw rate / lat-G), and how the new download would compare to the existing local dataset. Then asks the user which platform + how much, then fetches with a seeded held-out-devices train/val split.
when-to-load: When the user wants raw CAN data for a new platform, wants to refresh an existing one, OR asks open-ended questions like "what other cars could we use", "which platforms are good for lateral", "how much data do we have". NOT for decoding rlogs (that's the adapters in code/).
inputs: Initially none — the discovery view runs without arguments. After the user picks: a platform string (e.g. HYUNDAI_IONIQ_5) and optionally a target volume (--train N --val M).
outputs: <data_root>/raw/segments/<PLATFORM>/<device>/<route>/<idx>/rlog.zst (+ optional <val_data_root> mirror), split.json describing the split, and a manifest.json once build_manifest.py is run.
load-cost: ~250 tokens metadata, ~900 tokens body.
---

# download-rlog-data

## Source

All vehicle data comes from comma.ai's [`commaCarSegments`](https://huggingface.co/datasets/commaai/commaCarSegments) dataset on Hugging Face (MIT-licensed openpilot CAN logs). Files are Zstandard-compressed openpilot cereal logs:

```
https://huggingface.co/datasets/commaai/commaCarSegments/resolve/main/segments/<device>/<route>/<idx>/rlog.zst
```

## Layout in this repo

Both roots are declared in [webinar-meta/data-paths.json](../../data-paths.json) (single source of truth — the grading skill reads the same file):

```json
{
  "data_root": "data",
  "val_data_root": "data/val-data"
}
```

Paths are resolved relative to the repo root. The fetcher writes to:

```
<data_root>/raw/segments/<PLATFORM>/<device>/<route>/<idx>/rlog.zst   ← training pool
<val_data_root>/raw/segments/<PLATFORM>/<device>/<route>/<idx>/rlog.zst   ← held-out val (only with --val-split)
```

When using `--val-split`, a `split.json` describing the strategy + actual counts + held-out device IDs is written to both roots for traceability. Each platform folder also gets a `manifest.json` (devices / routes / segments / bytes / hours) once you run `build_manifest.py`. `data/` is gitignored — never commit downloads.

## How to use

The flow is **discover → decide → fetch → manifest**. Never skip discover — even when the user asks for a specific platform, run `recommend.py` first so the user sees the size relative to the existing dataset before committing to the download.

### 0. Discovery (always start here)

```bash
python webinar-meta/skills/download-rlog-data/recommend.py            # default — lateral-fidelity suitable, ranked, with local comparison
python webinar-meta/skills/download-rlog-data/recommend.py --by-oem   # group by OEM family
python webinar-meta/skills/download-rlog-data/recommend.py --all      # include "no decoded yaw rate" platforms
python webinar-meta/skills/download-rlog-data/recommend.py --local    # only what's already downloaded
```

Show the relevant slice to the user. Lateral-fidelity suitability has three tiers:
- **yes** (first-class) — Ford. `ret.yawRate` already populated in openpilot's `carstate.py`.
- **yes-patch** — Hyundai/Kia/Genesis, VW MQB family (Audi/Seat/Skoda). Yaw rate is in the shipped DBC but needs a ~10 LOC `carstate.py` patch to surface. Half-day of adapter work per OEM.
- **yes-partial** — Rivian. Decodable but newer/less proven.
- **no** — Toyota, Honda, GM, Subaru, Mazda, Nissan, Chrysler family. Would need chassis-bus reverse-engineering. Skip for this challenge.

Then **stop and ask the user** which platform(s) to fetch and roughly how much. Important to surface:
- Volume relative to the existing local dataset (e.g. "HYUNDAI_IONIQ_5 has 3594 segs / ~12 GB — your current local total is ~5 GB across all platforms, so a full Ioniq fetch would more than double your dataset and may imbalance the cohort").
- Whether they want everything, a balanced subset, or just a quick smoke download.
- Train/val target counts and split strategy (the default `held-out-devices` is almost always right — see step 2).
- Whether they want the YAML for the grading challenge updated to include this platform.

### 1. Get the segment index (once, or to refresh)

`fetch_platform.py` reads `/tmp/ccs_database.json`. The upstream dataset already publishes this file (~9 MB, 230 platforms, 188k segments) at its root — the builder just downloads it.

```bash
# Download (skips if /tmp/ccs_database.json already exists):
python webinar-meta/skills/download-rlog-data/build_ccs_database.py

# Force a refresh:
python webinar-meta/skills/download-rlog-data/build_ccs_database.py --force

# Inspect what's in the index:
python webinar-meta/skills/download-rlog-data/build_ccs_database.py --list-platforms
python webinar-meta/skills/download-rlog-data/build_ccs_database.py --inspect HYUNDAI_IONIQ_5
```

### 2. Download a platform

Whole-platform download (mirrors upstream layout, all segments):

```bash
python webinar-meta/skills/download-rlog-data/fetch_platform.py FORD_EXPLORER_MK6
```

Train/val split with held-out devices (default — physical cars never appear in both sides, best generalisation test):

```bash
python webinar-meta/skills/download-rlog-data/fetch_platform.py HYUNDAI_IONIQ_5 \
    --val-split --train 800 --val 400 --seed 42
```

To get the legacy F1/KB003 behaviour (random route shuffle, devices may overlap):

```bash
python webinar-meta/skills/download-rlog-data/fetch_platform.py HYUNDAI_IONIQ_5 \
    --val-split --split-strategy route-grouped
```

Held-out-devices is the default because, for openpilot CAN data, the same physical car = same sensor calibration + driver bias. Holding cars out yields the cleanest "does this generalise?" signal. The fetcher automatically falls back to `route-grouped` if a platform has fewer than 4 devices (the held-out strategy can't produce a useful split there). For HYUNDAI_IONIQ_5 (116 devices upstream), the default produces ~840 train / 417 val segments across 29 train devices and 11 val devices, with zero device overlap.

Both modes are **re-runnable** — they skip any segment already present with non-zero size, so interrupted runs continue where they left off. Default concurrency is 16 workers with 4 retries per file.

### 3. Build the manifest

After the download finishes:

```bash
python webinar-meta/skills/download-rlog-data/build_manifest.py FORD_EXPLORER_MK6
# writes data/raw/segments/FORD_EXPLORER_MK6/manifest.json
```

## Picking a platform

The upstream dataset includes many OEMs (Toyota, Honda, Ford, Hyundai, Tesla, VW, Rivian, GM, Subaru, Mazda, Chrysler, Nissan, …). Only **four OEM groups** ship a DBC with decodable yaw-rate values: Ford, Volkswagen MQB, Hyundai/Kia/Genesis, Rivian. Everything else needs chassis-bus reverse-engineering to be useful for lateral-fidelity work.

See `F1/KB002/public-data-sources/commacarsegments-per-oem-signals.md` for the full signal-coverage matrix and platform inventory (segment counts, hours, GB estimates per platform).

Current downloads in this repo:

| Platform | Mode | Decoded by |
|---|---|---|
| `TESLA_MODEL_3` | whole-platform | `code/adapter_tesla_rlog.py` (party DBC) |
| `FORD_MUSTANG_MACH_E_MK1` | whole-platform | `code/adapter_ford_rlog.py` |
| `FORD_F_150_LIGHTNING_MK1` | whole-platform | `code/adapter_ford_rlog.py` |
| `HYUNDAI_IONIQ_5` | train/val split (800/400, seed=42) | needs a Hyundai adapter (see F1/KB003/code/adapter_hyundai_rlog.py) |

## Adding a new platform end-to-end

1. **Confirm the platform exists** — `build_ccs_database.py --list-platforms` prints all 230 with segment counts. Exact string casing matters (e.g. `FORD_EXPLORER_MK6`, not `Ford Explorer`).
2. **Index**: `build_ccs_database.py` (downloads upstream `database.json` — covers everything).
3. **Download**: `fetch_platform.py <NAME>` (whole) or `--val-split` (train+val).
4. **Manifest**: `build_manifest.py <NAME>`.
5. **Decode**: pick or write an adapter. Existing adapters live in `code/adapter_*.py`. Ford and Hyundai/Kia/Genesis share families — a new Ford model usually reuses `adapter_ford_rlog.py`; a new Hyundai/Kia model usually reuses the Hyundai E-GMP CAN-FD adapter (in F1/KB003).
6. **Smoke-test one rlog**: `python code/inspect_rlog.py data/raw/segments/<PLATFORM>/<device>/<route>/0/rlog.zst` to confirm services and rates look sane.

## Why this lives as a skill (not just scripts in `code/`)

The downloaders in `code/fetch_*.py` are platform-pinned copies — four near-identical files. This skill replaces them with one generic script (`fetch_platform.py`) parameterised on the platform name, plus the missing pieces (`build_ccs_database.py`, the train/val variant collapsed into a flag). Old `code/fetch_*.py` copies still work; new platforms should use the skill.

## Files

| file | role |
|---|---|
| `recommend.py` | **Run this first.** Discovery + suitability view: which platforms are usable for lateral-fidelity, segment counts, size estimates, and what's already downloaded locally for comparison. |
| `build_ccs_database.py` | Downloads upstream `database.json` → `/tmp/ccs_database.json`. Also `--list-platforms` and `--inspect <PLATFORM>`. |
| `fetch_platform.py` | Generic parallel downloader. Default = whole-platform; `--val-split` = seeded held-out-devices train/val split (`--split-strategy route-grouped` for the F1/KB003 legacy behaviour). |
| `build_manifest.py` | Walks a downloaded platform tree and writes its `manifest.json` (totals, devices, routes, segments, hours). |
