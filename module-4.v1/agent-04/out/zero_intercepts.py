"""Zero out the residual head intercept to avoid CTE drift."""
import json
from pathlib import Path
p = Path(__file__).resolve().parents[1] / "models" / "v2_residual_head" / "coeffs.json"
d = json.loads(p.read_text())
for plat, cfg in d.items():
    cfg["intercept"] = 0.0
p.write_text(json.dumps(d, indent=2))
print("zeroed intercepts in", p)
