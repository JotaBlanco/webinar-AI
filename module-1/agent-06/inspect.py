"""Inspect sim.csv to understand schema."""
import pandas as pd
import numpy as np

p = '/Users/javiquix/Desktop/quixdev/webinar-AI/data/sim/segments/FORD_F_150_LIGHTNING_MK1/0b2c0bec9a28eb0f/00000001--82c7a5f419/34/sim.csv'
df = pd.read_csv(p)
print("shape:", df.shape)
print("columns:", df.columns.tolist())
print(df.head(5))
print("---tail---")
print(df.tail(3))
print("---dt---")
tcol = [c for c in df.columns if 't' in c.lower() and ('s' in c.lower() or 'sec' in c.lower() or 'time' in c.lower())]
print("time-like cols:", tcol)
for c in tcol:
    print(c, df[c].diff().describe())
