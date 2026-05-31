"""Build a route-level 80/20 train/dev split."""
import glob, random, json, os

paths = sorted(glob.glob('data/sim/segments/FORD_*/*/*/*/sim.csv'))
plat_routes = {}
for p in paths:
    parts = p.split('/')
    plat, dev, rt = parts[-5], parts[-4], parts[-3]
    plat_routes.setdefault(plat, {}).setdefault((dev, rt), []).append(p)

rng = random.Random(42)
train, dev = [], []
for plat, route_map in plat_routes.items():
    keys = sorted(route_map.keys())
    rng.shuffle(keys)
    n_dev = max(1, int(round(0.2 * len(keys))))
    dev_keys = set(keys[:n_dev])
    for k in keys:
        for p in route_map[k]:
            (dev if k in dev_keys else train).append(p)

print('train:', len(train), 'dev:', len(dev))
os.makedirs('artifacts', exist_ok=True)
with open('artifacts/split.json', 'w') as f:
    json.dump({'train': train, 'dev': dev}, f)
