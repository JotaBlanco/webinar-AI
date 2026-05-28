"""Build a flattened longitudinal dataset from sim.csv files.

Sample a manageable number of segments per platform, concatenate into one
DataFrame with platform + segment_id columns, save to out/long_dataset.parquet
(falls back to .csv if no pyarrow).
"""
import os
import glob
import random
import pandas as pd

random.seed(0)

ROOT = "/Users/javiquix/Desktop/quixdev/webinar-AI/raw-model/idea-02/agent-03"
SIM_ROOT = f"{ROOT}/data/sim/segments"
OUT_DIR = f"{ROOT}/out"
os.makedirs(OUT_DIR, exist_ok=True)

PLATFORMS = ["TESLA_MODEL_3", "FORD_MUSTANG_MACH_E_MK1", "FORD_F_150_LIGHTNING_MK1"]

# Sample budget: roughly even per platform.
MAX_PER_PLATFORM = 60

frames = []
for plat in PLATFORMS:
    csvs = glob.glob(f"{SIM_ROOT}/{plat}/*/*/*/sim.csv")
    random.shuffle(csvs)
    csvs = csvs[:MAX_PER_PLATFORM]
    print(f"{plat}: loading {len(csvs)} segments")
    for i, c in enumerate(csvs):
        try:
            df = pd.read_csv(c)
        except Exception as e:
            print(f"  skip {c}: {e}")
            continue
        # normalise brake column: Tesla = brake_pedal_state (numeric), Ford = brake_pressed (0/1)
        if "brake_pressed" in df.columns:
            df["brake"] = df["brake_pressed"].astype(float)
        elif "brake_pedal_state" in df.columns:
            # 2 == not pressed in Tesla typically? treat anything > 0 differently. Use raw value.
            df["brake"] = (df["brake_pedal_state"].astype(float) != 2).astype(float)
        else:
            df["brake"] = 0.0
        # standardise columns we'll use
        keep = ["t_s", "v_mps", "a_long_mps2", "accel_pedal_pct", "brake"]
        for k in keep:
            if k not in df.columns:
                df[k] = float("nan")
        df = df[keep].copy()
        df["platform"] = plat
        df["seg_id"] = f"{plat}_{i}"
        # numeric sanity
        df = df.dropna()
        if len(df) < 100:
            continue
        # compute dt
        df["dt"] = df["t_s"].diff().fillna(0.02)
        frames.append(df)

full = pd.concat(frames, ignore_index=True)
print(f"Total rows: {len(full):,}")
print(f"Segments: {full['seg_id'].nunique()}")
out_path = f"{OUT_DIR}/long_dataset.parquet"
try:
    full.to_parquet(out_path, index=False)
    print(f"Saved {out_path}")
except Exception as e:
    print(f"parquet fail ({e}), saving csv")
    full.to_csv(f"{OUT_DIR}/long_dataset.csv", index=False)
    print(f"Saved {OUT_DIR}/long_dataset.csv")
