#!/usr/bin/env python3
"""Bar plot of RMSE per regime per variant per platform."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

OUT = Path('/Users/javiquix/Desktop/quixdev/webinar-AI/webinar-angle-B/module-2/agent-01/out')
data = json.load(open(OUT/'summary.json'))

regimes = ['straight','steady','transient','all']
variants = ['V0','V1','V2','V3']

fig, axes = plt.subplots(1, 2, figsize=(12,5), sharey=True)
for ax, (plat, agg) in zip(axes, data.items()):
    x = np.arange(len(regimes))
    w = 0.2
    for i,v in enumerate(variants):
        vals = [agg[v][r][0]*1000 for r in regimes]
        ax.bar(x + (i-1.5)*w, vals, w, label=v)
    ax.set_xticks(x)
    ax.set_xticklabels(regimes)
    ax.set_title(plat.replace('_',' '))
    ax.set_ylabel('Yaw-rate residual RMSE [mrad/s]')
    ax.grid(True, axis='y', alpha=0.3)
    ax.legend()
fig.tight_layout()
fig.savefig(OUT/'variant_rmse.png', dpi=120)
print("wrote", OUT/'variant_rmse.png')
