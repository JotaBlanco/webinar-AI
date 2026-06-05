"""Tesla Model 3 parameter set for the CommonRoad model ladder.

Source of record is ../vehicle-tesla-model-3.md. Values below are taken from the
**openpilot carParams struct** decoded out of the rlogs themselves
(see ../adapters.md § "Confirmed by the rlog itself"). These are the values
comma.ai's Tesla interface ships — *not* placeholders. The confidence on KS- and
ST-level numbers is therefore "openpilot-canonical" rather than "regression
estimate".

For the workshop's step-6 fit, the cornering stiffnesses below are the *prior*
that calibration starts from, not the final value — but unlike the earlier
[low — fit from data] placeholders, this prior is a quantity comma.ai uses in
production today.
"""

from dataclasses import dataclass
from math import pi


@dataclass(frozen=True)
class TeslaModel3KS:
    """Parameters consumed by the KS model.

    Source: ../vehicle-tesla-model-3.md § "KS parameters" + openpilot Tesla
    interface (read from carParams in any rlog).
    """

    L: float = 2.875            # wheelbase [m]                 — openpilot-canonical
    delta_max: float = 0.55     # max road-wheel steering [rad] — regression, soft cap
    delta_dot_max: float = 0.4  # max steering rate [rad/s]     — non-binding in practice
    a_min: float = -10.0        # min long. acceleration [m/s²]
    a_max: float = 5.5          # max long. acceleration [m/s²] — LR AWD baseline

    @property
    def turning_radius_min(self) -> float:
        return self.L / abs(self._safe_tan(self.delta_max))

    @staticmethod
    def _safe_tan(x: float) -> float:
        from math import tan
        return tan(x)


@dataclass(frozen=True)
class TeslaModel3ST(TeslaModel3KS):
    """Parameters consumed by the ST model on top of KS.

    All values below are openpilot-canonical (read from carParams in any rlog).
    The cornering stiffnesses comma.ai ships are notably *higher* than typical
    regression-estimate priors — a clue that the openpilot integration assumes
    sticky OE rubber and modest sidewall compliance, consistent with the Tesla
    Model 3 stock setup.
    """

    m: float = 2035.0           # carParams.mass            — openpilot-canonical (loaded LR baseline)
    I_z: float = 3945.5         # carParams.rotationalInertia — openpilot-canonical
    l_f: float = 1.4375         # carParams.centerToFront    — openpilot-canonical (near-50/50)
    l_r: float = 1.4375         # = L - l_f                  — derived
    C_alpha_f: float = 222_882  # carParams.tireStiffnessFront — openpilot-canonical
    C_alpha_r: float = 352_332  # carParams.tireStiffnessRear  — openpilot-canonical
    i_s: float = 12.0           # carParams.steerRatio       — openpilot-canonical


# Convenience: the workshop's day-one parameter set.
TESLA_MODEL_3 = TeslaModel3ST()
TESLA_MODEL_3_KS = TeslaModel3KS()


# -----------------------------------------------------------------------------
# Ford Mustang Mach-E (MK1) — openpilot-canonical, decoded from rlog carParams
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class MachEKS:
    """KS-rung parameters for the Ford Mustang Mach-E (MK1).

    Source: ../vehicle-mach-e.md + carParams in any Mach-E rlog.

    Unlike Tesla, Ford IS a first-class openpilot port: the values below come
    from comma.ai's production interface, read straight out of the cereal
    `carParams` event in an actual commaCarSegments Mach-E rlog. There is no
    `[unverified]` flag on these numbers.
    """

    L: float = 2.984            # carParams.wheelbase [m]
    delta_max: float = 0.55     # max road-wheel steering [rad] — regression
    delta_dot_max: float = 0.4  # max steering rate [rad/s]     — non-binding
    a_min: float = -10.0
    a_max: float = 5.5

    @property
    def turning_radius_min(self) -> float:
        from math import tan
        return self.L / abs(tan(self.delta_max))


@dataclass(frozen=True)
class MachEST(MachEKS):
    """ST-rung parameters for the Ford Mustang Mach-E (MK1).

    All openpilot-canonical (carParams). The Mach-E is rear-biased
    (l_f / L ≈ 0.44), heavier than a Tesla Model 3 (2336 kg vs 2035 kg), and
    runs a higher steering ratio (17.0 vs 12.0) consistent with comfort-tuned
    rack geometry.
    """

    m: float = 2336.0           # carParams.mass
    I_z: float = 4879.05        # carParams.rotationalInertia
    l_f: float = 1.3130         # carParams.centerToFront
    l_r: float = 1.671          # = L - l_f
    C_alpha_f: float = 286_551  # carParams.tireStiffnessFront
    C_alpha_r: float = 355_912  # carParams.tireStiffnessRear
    i_s: float = 17.0           # carParams.steerRatio


MACH_E = MachEST()
MACH_E_KS = MachEKS()


# -----------------------------------------------------------------------------
# Ford F-150 Lightning (MK1) — openpilot-canonical, decoded from rlog carParams
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class F150LightningKS:
    """KS-rung parameters for the Ford F-150 Lightning (MK1).

    Source: ../vehicle-f150-lightning.md + carParams in any Lightning rlog.

    The Lightning is a full-size EV pickup: 3.7 m wheelbase, 3084 kg curb,
    nearly double the I_z of the Tesla. These extremes are exactly why it
    belongs in the workshop alongside the Tesla and Mach-E.
    """

    L: float = 3.70             # carParams.wheelbase [m]
    delta_max: float = 0.55
    delta_dot_max: float = 0.4
    a_min: float = -8.0         # truck — softer than a sedan
    a_max: float = 5.0          # standard-range LR figure

    @property
    def turning_radius_min(self) -> float:
        from math import tan
        return self.L / abs(tan(self.delta_max))


@dataclass(frozen=True)
class F150LightningST(F150LightningKS):
    """ST-rung parameters for the Ford F-150 Lightning (MK1)."""

    m: float = 3084.0           # carParams.mass — heavy
    I_z: float = 9903.37        # carParams.rotationalInertia — ~2.5x a sedan
    l_f: float = 1.628          # carParams.centerToFront
    l_r: float = 2.072          # = L - l_f
    C_alpha_f: float = 378_307  # carParams.tireStiffnessFront
    C_alpha_r: float = 469_878  # carParams.tireStiffnessRear
    i_s: float = 16.9           # carParams.steerRatio


F150_LIGHTNING = F150LightningST()
F150_LIGHTNING_KS = F150LightningKS()


# -----------------------------------------------------------------------------
# Hyundai Ioniq 5 (E-GMP) — openpilot-canonical, decoded from rlog carParams
# -----------------------------------------------------------------------------

@dataclass(frozen=True)
class Ioniq5KS:
    """KS-rung parameters for the Hyundai Ioniq 5 (E-GMP platform).

    Source: carParams in any Ioniq 5 rlog (first-class openpilot port).
    Notably rear-biased weight distribution (l_f/L ~ 0.40) and a tighter
    steering rack than the Fords (i_s ~ 14.3 vs 17.0).
    """

    L: float = 2.970            # carParams.wheelbase [m]
    delta_max: float = 0.55     # max road-wheel steering [rad]
    delta_dot_max: float = 0.4
    a_min: float = -10.0
    a_max: float = 5.5

    @property
    def turning_radius_min(self) -> float:
        from math import tan
        return self.L / abs(tan(self.delta_max))


@dataclass(frozen=True)
class Ioniq5ST(Ioniq5KS):
    """ST-rung parameters for the Hyundai Ioniq 5."""

    m: float = 2084.0           # carParams.mass
    I_z: float = 4311.97        # carParams.rotationalInertia
    l_f: float = 1.188          # carParams.centerToFront
    l_r: float = 1.782          # = L - l_f
    C_alpha_f: float = 178_034  # carParams.tireStiffnessFront
    C_alpha_r: float = 187_624  # carParams.tireStiffnessRear
    i_s: float = 14.26          # carParams.steerRatio


IONIQ_5 = Ioniq5ST()
IONIQ_5_KS = Ioniq5KS()


# -----------------------------------------------------------------------------
# Platform lookup
# -----------------------------------------------------------------------------

PARAM_BY_PLATFORM = {
    "TESLA_MODEL_3":             TESLA_MODEL_3,
    "FORD_MUSTANG_MACH_E_MK1":   MACH_E,
    "FORD_F_150_LIGHTNING_MK1":  F150_LIGHTNING,
    "HYUNDAI_IONIQ_5":           IONIQ_5,
}


if __name__ == "__main__":
    for label, p in [
        ("Tesla Model 3",            TESLA_MODEL_3),
        ("Ford Mustang Mach-E",      MACH_E),
        ("Ford F-150 Lightning",     F150_LIGHTNING),
    ]:
        print(f"\n{label} — openpilot-canonical parameter set")
        print(f"  L              = {p.L:.3f} m   (wheelbase)")
        print(f"  m              = {p.m:.0f} kg")
        print(f"  I_z            = {p.I_z:.1f} kg·m²")
        front_frac = p.l_f / p.L
        print(f"  l_f / l_r      = {p.l_f:.4f} / {p.l_r:.4f} m  "
              f"({front_frac*100:.0f}/{(1-front_frac)*100:.0f} f/r)")
        print(f"  C_alpha_f / r  = {p.C_alpha_f:,.0f} / {p.C_alpha_r:,.0f} N/rad")
        print(f"  i_s            = {p.i_s:.1f}")
        print(f"  delta_max      = ±{p.delta_max:.3f} rad  ({p.delta_max * 180 / pi:.1f}°)")
        print(f"  min turning R  ≈ {p.turning_radius_min:.2f} m")
