from pathlib import Path

body = """# Final-model bundle — agent-01

Model: V1 single-track with understeer + steering-rate lead.

    delta_eff = delta_road_rad + tau * d(delta_road)/dt
    yaw_pred  = gain * v * delta_eff / (L_eff + K_us * v^2) + bias

Per-platform coefficients live in `coeffs.json`. Tesla pass-through to V0
(no independent truth channel on Tesla sim).

See `module-2.v3/agent-01/REPORT.md` for the full write-up and KPIs.
"""

target = Path("/Users/javiquix/Desktop/quixdev/webinar-AI/module-2.v3/agent-01/final-model/REPORT.md")
target.write_text(body)
print("wrote", target, target.stat().st_size, "bytes")
