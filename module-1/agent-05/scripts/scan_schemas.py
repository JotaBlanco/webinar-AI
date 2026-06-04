"""Categorize all sim.csv files by their schema."""
import os
from collections import defaultdict

base = '/Users/javiquix/Desktop/quixdev/webinar-AI/module-1/agent-05/data/sim/segments'
schemas = defaultdict(list)
for root, _, files in os.walk(base):
    for f in files:
        if f == 'sim.csv':
            p = os.path.join(root, f)
            with open(p) as fp:
                hdr = fp.readline().strip()
            schemas[hdr].append(p)

for hdr, paths in schemas.items():
    print(f"\nSCHEMA ({len(paths)} files):")
    print(f"  {hdr}")
    print(f"  ex: {paths[0]}")
