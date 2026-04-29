"""Events: turn-by-turn shocks and structural changes.

Each event corresponds to something Reisman documents — frost years, drought,
the AHA "qualified" endorsement (p. 7), the varroa mite (p. 79), and the
2014-2016 Almond Board panic that raised the levy by 33% (p. 7). Events fire
probabilistically, but the seed can be fixed for reproducibility (used by the
California 2000s scenario, which replays the historical sequence in order).
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, List, Optional

from .market import Market
from .orchard import Orchard


@dataclass
class Event:
    """A named, dated effect on the world.

    `apply` mutates the market and/or the list of orchards. `description` is
    shown to the player; cite Reisman where applicable so the educational
    purpose is visible.
    """
    name: str
    description: str
    apply: Callable[[Market, List[Orchard], int], None]


# ----- Library of events -----------------------------------------------------

def aha_endorsement_event() -> Event:
    """One-time demand boost analogous to the 1994 AHA endorsement (Reisman p. 7)."""
    def _apply(market: Market, orchards: List[Orchard], year: int) -> None:
        market.baseline_demand *= 1.35
    return Event(
        name="AHA 'qualified' endorsement",
        description=(
            "After heavy industry lobbying, the American Heart Association "
            "issues a 'qualified' health endorsement of almonds. Baseline "
            "demand rises 35%. (Reisman p. 7.)"
        ),
        apply=_apply,
    )


def drought_event(severity: float = 0.20) -> Event:
    """One-year yield penalty on intensive orchards; rainfed barely affected.

    Reisman discusses California's 2014-16 drought (p. 7-8). Intensive
    orchards take the hit; rainfed plantings, planted at the margins where
    rainfall is the only water anyway, shrug it off. We model this as a
    one-year yield multiplier on intensive cohorts; severity is the fraction
    of yield lost, where 1.0 = catastrophic.
    """
    def _apply(market: Market, orchards: List[Orchard], year: int) -> None:
        loss = max(0.0, min(0.6, severity * 0.30))
        for o in orchards:
            o.current_year_intensive_yield_modifier *= (1 - loss)
    return Event(
        name="Drought year",
        description=(
            "Multi-year drought tightens water allocations. Intensive orchards "
            "lose yield; rainfed Spanish-style plantings shrug it off. "
            "(Reisman ch. 2.)"
        ),
        apply=_apply,
    )


def varroa_mite_event() -> Event:
    """Pollination-cost hike for orchards depending on trucked-in honeybees."""
    def _apply(market: Market, orchards: List[Orchard], year: int) -> None:
        # Players already pay $250/acre for hives; varroa pushes it up.
        # Encoded as a one-shot capital hit on California-style orchards.
        for o in orchards:
            from .orchard import Intensification
            need_bees = sum(
                c.acres for c in o.cohorts
                if c.regime != Intensification.RAINFED and c.is_productive(year)
            ) if not o.uses_self_compatible_variety else 0
            o.capital -= 100 * need_bees
    return Event(
        name="Varroa mite outbreak",
        description=(
            "Varroa destructor sweeps managed hives. Beekeepers raise rental "
            "prices to cover treatment. Self-compatible varieties dodge the bill. "
            "(Reisman p. 79, 92.)"
        ),
        apply=_apply,
    )


def china_export_boom_event() -> Event:
    """Demand expansion as Almond Board investments in Asian markets pay off."""
    def _apply(market: Market, orchards: List[Orchard], year: int) -> None:
        market.baseline_demand *= 1.20
    return Event(
        name="China export market opens",
        description=(
            "The Almond Board's investment in Asian advertising pays off. "
            "Baseline demand rises 20%. (Reisman p. 8-9.)"
        ),
        apply=_apply,
    )


def panic_levy_increase_event() -> Event:
    """Almond Board sees the projected glut and raises the levy 33%.

    Reisman p. 7: "By 2016 the Almond Board was so panicked about the increase
    in plantings that it sought approval from the USDA to increase the
    assessment by 33 percent (from three to four cents per pound)."
    """
    def _apply(market: Market, orchards: List[Orchard], year: int) -> None:
        market.levy_rate *= 1.33
    return Event(
        name="Panic levy increase",
        description=(
            "The Almond Board, alarmed by nursery-sale projections, gets USDA "
            "approval to raise the per-pound assessment by 33%. More marketing "
            "spend will follow. (Reisman p. 7.)"
        ),
        apply=_apply,
    )


def frost_event() -> Event:
    """Spring frost takes ~25% off yield for one year, all regimes."""
    def _apply(market: Market, orchards: List[Orchard], year: int) -> None:
        for o in orchards:
            o.current_year_yield_modifier *= 0.75
    return Event(
        name="Late spring frost",
        description=(
            "Cold snap during bloom. Yields drop ~25% across the board. "
            "Late-flowering Spanish varieties suffer somewhat less in reality, "
            "though here we model an equal hit."
        ),
        apply=_apply,
    )


# ----- Event scheduling -----------------------------------------------------

@dataclass
class EventSchedule:
    """Either a fixed sequence (for reproducible scenarios) or a stochastic
    process (for free play)."""
    fixed: Optional[dict] = None  # year -> List[Event]
    stochastic_rate: float = 0.30  # chance of drawing one random event per year
    rng: Optional[random.Random] = None

    def events_for_year(self, year: int) -> List[Event]:
        out: List[Event] = []
        if self.fixed and year in self.fixed:
            out.extend(self.fixed[year])
        if self.rng is not None and self.rng.random() < self.stochastic_rate:
            roster = [drought_event, varroa_mite_event, frost_event]
            choice = self.rng.choice(roster)
            out.append(choice())
        return out
