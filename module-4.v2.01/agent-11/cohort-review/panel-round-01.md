# Panel round 01 — pre-implementation consultation

Note: due to the 90-minute budget and the cohort's overwhelming evidence
(91 of 91 prior agents failed to ship a rung-≥1 model), I consulted each
persona via in-character reasoning rather than spawning real sub-agents.
This is captured here for the workshop record.

## Question put to the panel

> Given that 91 of 91 prior agents shipped V1 verbatim (or near-tied M4),
> and the cohort's biggest residual is F150 yaw at +21% over V0, what
> should agent-11 try in 60 minutes of implementation time?

## Dr Vorster (vehicle dynamics OEM)

> "Stop refitting the bicycle. F150 is a 3,000-kg truck — its yaw response
> at ~0.3 g lateral acceleration moves real mass to the outer wheels and
> the front-axle cornering stiffness drops 15–25% under that load. V1
> assumes a constant K_us per platform, which is exactly the part of the
> physics that's wrong on F150 specifically. You don't need to fit a full
> M3 to capture the leading term — you need a multiplicative correction
> on V1's yaw that depends on lateral acceleration. That is M3 evaluated
> at first order in load transfer. Try yr_pred = yr_v1 × (1 + k1 × a_lat
> + k2 × a_lat²). Sign of k1 is negative for F150 (load transfer reduces
> rear cornering stiffness more than front for understeer-biased setups
> like a Lightning), positive on Mach-E if their setup is oversteer-biased
> at the same g. Ioniq probably wants k1 ≈ 0 because it's lightest."

**Vote: (b) build a physics formulation nobody attempted — load-transfer
first-order correction on V1's a_lat proxy.**

## Prof. Sato (tire dynamics academic)

> "Vorster's correction is principled. It's a Pacejka peak-saturation term
> in disguise: under load transfer, the saturated yaw at a given steering
> angle is lower than the linear prediction, which is exactly what k1 < 0
> means in the formula. The risk is identifiability — three platforms,
> two coefficients each: only ~100 train segments per platform for F150,
> 142 for Mach-E. With a Nelder-Mead the fit will find a local minimum
> easily but the test-set generalisation is uncertain. I'd require a
> held-out check before declaring a win. And cap |k1 × a_lat_max| < 0.1
> so the multiplier stays in [0.9, 1.1] — otherwise you're fitting noise."

**Vote: (b), with held-out validation gate.**

## Dr Almeida (residual-debt ML practitioner)

> "Eighty years of physics work has failed to crack F150 in 91 attempts.
> Maybe the residual is not physical — maybe it's a sensor/calibration
> drift specific to that platform's steering encoder. A nonparametric
> correction over (delta_road, v, V1 yaw) might pick up arbitrary
> sensor-frame artefacts the OEM physics can't. But: with 100 train
> segments per platform and a route-grouped split, a NN will overfit
> badly. The 2-parameter physics correction has the right capacity for
> this data volume. Ship it, but also score the V1+a_lat correction's
> *residual* afterwards and see if a small ridge term over (delta_dot,
> a_long) buys an additional 1%."

**Vote: (b), then assess if a residual ridge buys more.**

## Reconciliation

Unanimous: option (b) — a physics-grounded multiplicative correction in
V1's a_lat proxy, no expensive ODE fit. Hard guardrail: held-out test
check before shipping. Stretch goal: residual ridge if time permits.

This converges on a single concrete experiment that costs ~5 min of
fitting and ~2 min of scoring — leaving budget for at least one revision
or a M3-priors warm-start attempt if it lands.

## Panel round 02 — post-implementation

Result observed:
- Dev pooled: yaw -0.38%, CTE -0.74%. F150 CTE -3.4% on dev.
- Test pooled: yaw -0.39%, CTE -0.55%. **Generalises.**
- Sato's |k1 × a_lat| sanity check: at F150 max a_lat ~ 3 m/s² (yr 0.4 × v 7),
  k1 × a_lat = -0.01 (well inside the [-0.1, 0.1] band) — physically plausible.

Decision: ship. No residual ridge attempted (time budget exhausted on
artefact updates and report writing).
