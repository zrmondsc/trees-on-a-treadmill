"""Archetypes: NPC farmer behaviors that produce the macro-treadmill.

Reisman's argument is that the treadmill emerges from individually rational
decisions interacting through the market. To recreate that, we need NPCs
whose decision rules differ. Three archetypes drawn from the book:

- SpanishRainfedSmallholder (p. 8-9): low-input, polyvalent, slow to adopt.
  Operates almonds as a side hustle alongside wage work. Yields are
  unreliable but costs are negligible. Anticipation weight: low.
- CaliforniaIntensiveGrower: classic Cochrane-treadmill subject. Watches
  prices and projections closely; adopts new inputs aggressively when peers do.
- InvestorMegaplanting (p. 12): post-2014 corporate entrant. Plants with
  near-infinite capital, follows California recipe regardless of margins,
  amplifies the boom-bust.

Each archetype implements `decide(year, market, self_orchard) -> Decision`,
where Decision describes the actions to take this turn. The engine resolves
them all together.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .market import Market
from .orchard import Intensification, Orchard


@dataclass
class Decision:
    """Actions an orchard will take this turn."""
    plant_acres: float = 0.0
    plant_regime: Intensification = Intensification.INTENSIVE
    remove_acres: float = 0.0
    marketing_contribution: float = 0.0  # voluntary top-up beyond the levy
    switch_to_self_compatible: bool = False  # one-time flip


# --- Helpers ----------------------------------------------------------------

def _signal(market: Market, anticipation_weight: float) -> float:
    """Combine current price and projected supply growth into a planting
    signal. Higher = more reason to plant.

    `anticipation_weight` is how much the archetype trusts forward-looking
    nursery-sale projections. A Spanish rainfed grower (low weight) cares
    mainly about today's price; a California intensive grower (high weight)
    is already adjusting to forecasts that haven't materialized yet.
    """
    # Price signal: above reference is a "go" signal.
    price_signal = (market.current_price / market.reference_price) - 1.0

    # Anticipatory signal: positive growth in projected supply is bad — it
    # means the glut is coming. So a forward-looking farmer plants LESS when
    # projected growth is high.
    growth = market.projected_supply_growth_5yr()
    anticipation_signal = -growth  # invert: glut coming = don't plant

    return (1 - anticipation_weight) * price_signal + anticipation_weight * anticipation_signal


# --- Archetype decision functions -------------------------------------------

def decide_spanish_rainfed(year: int, market: Market, o: Orchard) -> Decision:
    """The 'crop of last resort' farmer (Reisman p. 8-9).

    Plants slowly when prices are good. Doesn't watch projections. Never
    intensifies on their own — but EU subsidies might push them.
    """
    d = Decision(plant_regime=Intensification.RAINFED)
    if o.bankrupt:
        return d
    signal = _signal(market, anticipation_weight=0.10)
    if signal > 0.20 and o.capital > 50_000:
        # Plant a modest 5-15 acres
        d.plant_acres = min(15, o.capital / 1_000)
    return d


def decide_california_intensive(year: int, market: Market, o: Orchard) -> Decision:
    """Cochrane's classic subject (Reisman p. 14).

    Watches the spot price AND nursery-sale projections. Adopts intensive
    practices when peers do. Slow to remove.
    """
    d = Decision(plant_regime=Intensification.INTENSIVE)
    if o.bankrupt:
        return d
    signal = _signal(market, anticipation_weight=0.50)

    # Keep ~2 years of operating costs in reserve
    reserve = o.operating_cost(year) * 2
    investable = max(0, o.capital - reserve)

    if signal > 0.10 and investable > 50_000:
        max_affordable = investable / 9_000  # intensive establishment cost
        d.plant_acres = min(150, max_affordable)
    elif signal < -0.30 and o.bearing_acres(year) > 100:
        d.remove_acres = min(50, o.total_acres() * 0.10)
    return d


def decide_investor_megaplanting(year: int, market: Market, o: Orchard) -> Decision:
    """Post-2014 corporate entrant (Reisman p. 12).

    Almost ignores price signals: capital is plentiful and the strategy is
    long-horizon land accumulation. Plants superintensive aggressively when
    the price is anywhere near reference and projections aren't apocalyptic.
    """
    d = Decision(plant_regime=Intensification.SUPERINTENSIVE)
    if o.bankrupt:
        return d
    growth = market.projected_supply_growth_5yr()
    # Investors keep a working-capital reserve ~3 years of operating costs
    annual_op_cost = o.operating_cost(year)
    reserve = annual_op_cost * 3
    investable = max(0, o.capital - reserve)
    if market.current_price > market.reference_price * 0.7 and growth < 0.50:
        # Plant up to whatever investable capital allows, capped at 200 acres/yr
        max_acres = investable / 14_000  # superintensive establishment cost
        d.plant_acres = min(200, max_acres)
    return d


# --- Archetype registry -----------------------------------------------------

@dataclass
class Archetype:
    name: str
    decide: callable
    starting_capital: float
    starting_acres: float
    starting_regime: Intensification
    anticipation_weight: float
    uses_self_compatible: bool = False


SPANISH_RAINFED = Archetype(
    name="Spanish rainfed smallholder",
    decide=decide_spanish_rainfed,
    starting_capital=80_000,
    starting_acres=20,
    starting_regime=Intensification.RAINFED,
    anticipation_weight=0.10,
    uses_self_compatible=True,  # post-1986 Guara variety
)

CALIFORNIA_INTENSIVE = Archetype(
    name="California intensive grower",
    decide=decide_california_intensive,
    starting_capital=600_000,
    starting_acres=150,
    starting_regime=Intensification.INTENSIVE,
    anticipation_weight=0.50,
    uses_self_compatible=False,  # depends on trucked-in honeybees
)

INVESTOR_MEGAPLANTING = Archetype(
    name="Investor megaplanting",
    decide=decide_investor_megaplanting,
    starting_capital=12_000_000,
    starting_acres=300,
    starting_regime=Intensification.SUPERINTENSIVE,
    anticipation_weight=0.30,
    uses_self_compatible=False,
)


# Default age (in years) of starting trees. Picked so the trees are mid-prime
# when the simulation begins, mirroring an established orchard at year 0.
DEFAULT_STARTING_TREE_AGE = 10


def make_orchard(arch: Archetype, name: Optional[str] = None,
                 planting_year: Optional[int] = None) -> Orchard:
    """Spin up an Orchard pre-populated for the archetype.

    `planting_year` defaults to -DEFAULT_STARTING_TREE_AGE so the starting
    acres are already mature when year 0 begins.
    """
    from .orchard import TreeCohort
    if planting_year is None:
        planting_year = -DEFAULT_STARTING_TREE_AGE
    o = Orchard(
        name=name or arch.name,
        capital=arch.starting_capital,
        anticipation_weight=arch.anticipation_weight,
        uses_self_compatible_variety=arch.uses_self_compatible,
    )
    o.cohorts.append(TreeCohort(
        planting_year=planting_year,
        acres=arch.starting_acres,
        regime=arch.starting_regime,
    ))
    return o
