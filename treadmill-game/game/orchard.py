"""Orchard: per-farm state.

A central design decision: trees are tracked as *age cohorts*, not just total
acres. This matters because Reisman's anticipatory mechanism (p. 14) hinges on
the fact that almond trees take ~4 years to bear fruit and ~20 years to remove.
A planting decision today commits capital for two decades and locks in supply
that will arrive on the market years from now. You cannot un-plant on a whim.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Intensification(Enum):
    """Three production regimes, drawn from Reisman's California/Spain contrast.

    RAINFED: Spain's traditional system (p. 8-9) — rugged, low-input, often
        on marginal land. Low yields but very low costs. Resilient to price
        crashes because there's little to lose.
    INTENSIVE: California's standard model — drip irrigation, agrichemicals,
        trucked-in pollination, mechanized harvest.
    SUPERINTENSIVE: Hedgerow plantings (p. 92), the most capital-intensive
        regime. Very high yields, very high salt accumulation, very high
        debt service.
    """
    RAINFED = "rainfed"
    INTENSIVE = "intensive"
    SUPERINTENSIVE = "superintensive"


# Yield characteristics by regime, in lb/acre at maturity (rough Reisman/USDA orders).
BASE_YIELD_LB_PER_ACRE: Dict[Intensification, float] = {
    Intensification.RAINFED: 250,
    Intensification.INTENSIVE: 2_400,
    Intensification.SUPERINTENSIVE: 3_500,
}

# Annual operating cost in USD/acre.
BASE_COST_PER_ACRE: Dict[Intensification, float] = {
    Intensification.RAINFED: 200,
    Intensification.INTENSIVE: 2_800,
    Intensification.SUPERINTENSIVE: 4_500,
}

# Establishment cost (sunk, year 0) in USD/acre — saplings, prep, irrigation
# infrastructure. From Reisman p. 14: "the upfront investment for an orchard
# is quite high, as growers purchase costly saplings rather than seeds."
ESTABLISHMENT_COST_PER_ACRE: Dict[Intensification, float] = {
    Intensification.RAINFED: 800,
    Intensification.INTENSIVE: 9_000,
    Intensification.SUPERINTENSIVE: 14_000,
}

# Years from planting to first commercial harvest.
ESTABLISHMENT_YEARS = 4

# Productive lifespan of a tree before steep decline.
PRODUCTIVE_YEARS = 22

# Yield ramp: fraction of mature yield as a function of age in years.
# 0-3: 0%. 4: 30%. 5: 60%. 6: 90%. 7-22: 100%. 23+: declines 5%/yr.
def yield_factor(age: int) -> float:
    if age < ESTABLISHMENT_YEARS:
        return 0.0
    if age == 4:
        return 0.30
    if age == 5:
        return 0.60
    if age == 6:
        return 0.90
    if age <= 22:
        return 1.0
    # Decline phase
    return max(0.0, 1.0 - 0.05 * (age - 22))


@dataclass
class TreeCohort:
    """A block of trees planted in the same year, same regime."""
    planting_year: int
    acres: float
    regime: Intensification

    def age(self, current_year: int) -> int:
        return current_year - self.planting_year

    def is_productive(self, current_year: int) -> bool:
        return yield_factor(self.age(current_year)) > 0

    def yield_lb_per_acre(self, current_year: int) -> float:
        return BASE_YIELD_LB_PER_ACRE[self.regime] * yield_factor(self.age(current_year))

    def total_yield_lb(self, current_year: int) -> float:
        return self.acres * self.yield_lb_per_acre(current_year)


@dataclass
class Orchard:
    """A single farm — player or NPC.

    Capital is the running checking account. When it goes negative the orchard
    is in debt; debt above a threshold means bankruptcy ("get out of the
    game," Reisman p. 14).
    """
    name: str
    cohorts: List[TreeCohort] = field(default_factory=list)
    capital: float = 250_000.0
    debt_threshold: float = -500_000.0  # bankruptcy below this

    # Lock-in state (Ch. 2-3 of Reisman)
    salt_burden: float = 0.0           # 0-1; intensive irrigation accumulates
    pesticide_dependency: float = 0.0  # 0-1; pesticide-treadmill within the treadmill
    uses_self_compatible_variety: bool = False  # Spanish Guara-line option

    # One-year-only yield modifier set by events (drought, frost). Reset at
    # the end of each settle(). 1.0 = no penalty.
    current_year_yield_modifier: float = 1.0
    # Per-regime modifier (drought hits intensive harder)
    current_year_intensive_yield_modifier: float = 1.0

    # Anticipation: each archetype weights future supply projections more or less
    # heavily. Spanish smallholders (anticipation_weight ~ 0.1) barely react to
    # forecasts; California intensives (~ 0.7) react sharply.
    anticipation_weight: float = 0.5

    # Bookkeeping
    bankrupt: bool = False
    cumulative_profit: float = 0.0

    # --- Geometry helpers -----------------------------------------------------

    def total_acres(self) -> float:
        return sum(c.acres for c in self.cohorts)

    def bearing_acres(self, current_year: int) -> float:
        return sum(c.acres for c in self.cohorts if c.is_productive(current_year))

    def acres_by_regime(self) -> Dict[Intensification, float]:
        out: Dict[Intensification, float] = {r: 0.0 for r in Intensification}
        for c in self.cohorts:
            out[c.regime] += c.acres
        return out

    def dominant_regime(self) -> Optional[Intensification]:
        by_regime = self.acres_by_regime()
        if not any(by_regime.values()):
            return None
        return max(by_regime, key=by_regime.get)

    # --- Production -----------------------------------------------------------

    def produce(self, current_year: int) -> float:
        """Total lb of almonds produced this year, summed across cohorts.
        Honors any one-year event modifiers."""
        total = 0.0
        for c in self.cohorts:
            y = c.total_yield_lb(current_year) * self.current_year_yield_modifier
            if c.regime != Intensification.RAINFED:
                y *= self.current_year_intensive_yield_modifier
            total += y
        return total

    def operating_cost(self, current_year: int) -> float:
        """Annual operating cost, scaled for regime, salt, and pollination."""
        cost = 0.0
        for c in self.cohorts:
            base = BASE_COST_PER_ACRE[c.regime] * c.acres
            # Salt-leaching surcharge: intensive/superintensive only.
            # Reisman p. 65-66: 15-30% additional irrigation as a leaching fraction.
            if c.regime != Intensification.RAINFED:
                base *= 1.0 + 0.20 * self.salt_burden
            # Pollination need: California-style intensive depends on trucked
            # honeybees; Spanish self-compatible varieties don't (Reisman p. 92).
            if c.regime != Intensification.RAINFED and not self.uses_self_compatible_variety:
                base += 250 * c.acres  # ~$250/acre/year for hive rental
            cost += base
        return cost

    # --- Actions --------------------------------------------------------------

    def plant(self, year: int, acres: float, regime: Intensification) -> bool:
        """Plant new acres. Returns True if successful, False if too expensive."""
        cost = ESTABLISHMENT_COST_PER_ACRE[regime] * acres
        if self.capital < cost:
            return False
        self.capital -= cost
        self.cohorts.append(TreeCohort(planting_year=year, acres=acres, regime=regime))
        return True

    def remove(self, current_year: int, acres: float, prefer_old: bool = True) -> float:
        """Push out trees. Returns acres actually removed.

        Removal is roughly free (no payment, but also no salvage). Reisman
        notes growers do tear out unprofitable orchards but only after years
        of staring at low prices.
        """
        # Sort cohorts: oldest first (or youngest first, if we're cutting losses
        # on a recent gamble that's not paying off).
        if prefer_old:
            order = sorted(self.cohorts, key=lambda c: c.planting_year)
        else:
            order = sorted(self.cohorts, key=lambda c: -c.planting_year)
        removed = 0.0
        remaining = acres
        for c in order:
            if remaining <= 0:
                break
            take = min(c.acres, remaining)
            c.acres -= take
            removed += take
            remaining -= take
        # Drop any zero-acre cohorts
        self.cohorts = [c for c in self.cohorts if c.acres > 0.001]
        return removed

    def settle(self, year: int, price_per_lb: float, marketing_levy_per_lb: float) -> float:
        """Resolve revenue, costs, and levy for the year. Returns net profit."""
        production_lb = self.produce(year)
        revenue = production_lb * price_per_lb
        costs = self.operating_cost(year)
        # Levy applies to bearing California-style orchards (federal marketing
        # order). Reisman p. 15: "force of law to collect its dues."
        levy_eligible_lb = sum(
            c.total_yield_lb(year) for c in self.cohorts
            if c.regime != Intensification.RAINFED
        )
        levy = levy_eligible_lb * marketing_levy_per_lb
        profit = revenue - costs - levy
        self.capital += profit
        self.cumulative_profit += profit

        # Lock-in dynamics: salt and pesticide dependence accumulate while
        # intensive acres are in production.
        intensive_acres = sum(
            c.acres for c in self.cohorts
            if c.regime != Intensification.RAINFED and c.is_productive(year)
        )
        if intensive_acres > 0:
            # Salt accumulates ~5%/yr unless fully managed
            self.salt_burden = min(1.0, self.salt_burden + 0.05)
            # Pesticide treadmill (Reisman p. 76, 88): each year of intensive
            # use erodes effectiveness, demanding more.
            self.pesticide_dependency = min(1.0, self.pesticide_dependency + 0.04)
        else:
            self.salt_burden = max(0.0, self.salt_burden - 0.02)
            self.pesticide_dependency = max(0.0, self.pesticide_dependency - 0.02)

        if self.capital < self.debt_threshold:
            self.bankrupt = True

        # Reset one-year-only event modifiers
        self.current_year_yield_modifier = 1.0
        self.current_year_intensive_yield_modifier = 1.0
        return profit

    # --- Reporting ------------------------------------------------------------

    def status_line(self, year: int) -> str:
        regime = self.dominant_regime()
        regime_str = regime.value if regime else "fallow"
        return (
            f"{self.name:24s} acres={self.total_acres():7.0f}  "
            f"bearing={self.bearing_acres(year):7.0f}  "
            f"capital=${self.capital:>11,.0f}  "
            f"regime={regime_str:14s}  "
            f"salt={self.salt_burden:.2f}  bankrupt={self.bankrupt}"
        )
