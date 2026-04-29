"""Engine: per-turn simulation loop.

Each year:
    1. Apply scheduled events (drought, AHA endorsement, varroa, frost, ...)
    2. Update the market's forward-looking projection from current cohorts
    3. Each NPC archetype decides; the player decides last (so they see NPC
       actions as part of the world; in interactive play, the player decides
       first within the same year).
    4. Resolve plantings and removals.
    5. Compute total bearing supply across all orchards.
    6. Marketing: spend the levy, decay last year's lift.
    7. Market clears, price posts.
    8. Each orchard settles: revenue - costs - levy.
    9. Record history.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from .archetypes import Archetype, Decision, make_orchard
from .events import EventSchedule
from .market import Market
from .orchard import Intensification, Orchard, ESTABLISHMENT_YEARS


@dataclass
class TurnReport:
    """Everything that happened this year, for display and debugging."""
    year: int
    price: float
    total_supply_million_lb: float
    marketing_spend: float
    new_plantings_acres: float
    bankruptcies: List[str] = field(default_factory=list)
    fired_events: List[str] = field(default_factory=list)
    orchard_lines: List[str] = field(default_factory=list)


@dataclass
class GameState:
    """Top-level container."""
    year: int = 0
    market: Market = field(default_factory=Market)
    orchards: List[Orchard] = field(default_factory=list)
    archetypes: List[Archetype] = field(default_factory=list)
    schedule: Optional[EventSchedule] = None
    player_index: Optional[int] = None  # which orchard is the player's

    def player_orchard(self) -> Optional[Orchard]:
        if self.player_index is None:
            return None
        return self.orchards[self.player_index]


# --- Setup helpers ----------------------------------------------------------

def setup_game(archetypes: List[Archetype], player_archetype: Optional[Archetype] = None,
               schedule: Optional[EventSchedule] = None,
               player_name: str = "You") -> GameState:
    """Create a GameState with one orchard per archetype, plus an optional
    extra player-controlled orchard."""
    state = GameState(schedule=schedule)
    for arch in archetypes:
        state.orchards.append(make_orchard(arch))
        state.archetypes.append(arch)
    if player_archetype is not None:
        state.orchards.append(make_orchard(player_archetype, name=player_name))
        state.archetypes.append(player_archetype)
        state.player_index = len(state.orchards) - 1
    # Initial market projection from starting cohorts
    update_market_projection(state)
    return state


# --- Projection helper ------------------------------------------------------

def update_market_projection(state: GameState) -> None:
    """Compute industry-wide bearing acres for years current+0 .. current+10.

    This is the equivalent of the Almond Board's nursery-sale forecast.
    Reisman p. 14: "estimates of production three, five, and ten years down
    the road." We project deterministically from existing cohorts: nothing
    new will be planted in this calculation, so it represents the "if no one
    plants anything more from today" supply path.
    """
    horizons = list(range(0, 11))
    proj = []
    for h in horizons:
        future_year = state.year + h
        bearing = 0.0
        for o in state.orchards:
            if o.bankrupt:
                continue
            for c in o.cohorts:
                if c.is_productive(future_year):
                    bearing += c.acres
        proj.append(bearing)
    state.market.update_projection(proj)


# --- The turn loop ----------------------------------------------------------

def run_turn(state: GameState, player_decision: Optional[Decision] = None) -> TurnReport:
    """Advance the simulation by one year. Returns a report.

    If `player_decision` is None and there's a player_index, NPC logic is used
    for the player too (useful for headless scenarios).
    """
    report = TurnReport(year=state.year, price=0.0, total_supply_million_lb=0.0,
                        marketing_spend=0.0, new_plantings_acres=0.0)

    # Step 1: events
    if state.schedule is not None:
        for e in state.schedule.events_for_year(state.year):
            e.apply(state.market, state.orchards, state.year)
            report.fired_events.append(f"{e.name}: {e.description}")

    # Step 2: refresh projection so archetypes see the same forecast the
    # player does
    update_market_projection(state)

    # Step 3: collect decisions
    decisions: List[Decision] = []
    for i, (orchard, arch) in enumerate(zip(state.orchards, state.archetypes)):
        if i == state.player_index and player_decision is not None:
            decisions.append(player_decision)
        else:
            decisions.append(arch.decide(state.year, state.market, orchard))

    # Step 4: apply plantings/removals
    new_plantings_total = 0.0
    for orchard, dec in zip(state.orchards, decisions):
        if dec.switch_to_self_compatible:
            orchard.uses_self_compatible_variety = True
        if dec.remove_acres > 0:
            orchard.remove(state.year, dec.remove_acres)
        if dec.plant_acres > 0:
            ok = orchard.plant(state.year, dec.plant_acres, dec.plant_regime)
            if ok:
                new_plantings_total += dec.plant_acres
    report.new_plantings_acres = new_plantings_total

    # Step 5: total bearing supply (lb -> million lb)
    total_supply_lb = sum(o.produce(state.year) for o in state.orchards if not o.bankrupt)
    total_supply_million = total_supply_lb / 1_000_000
    report.total_supply_million_lb = total_supply_million

    # Step 6: marketing — collect levy from prior year's bearing intensive
    # production, plus voluntary contributions
    levy_eligible_lb = 0.0
    for o in state.orchards:
        if o.bankrupt:
            continue
        for c in o.cohorts:
            if c.regime != Intensification.RAINFED and c.is_productive(state.year):
                levy_eligible_lb += c.total_yield_lb(state.year)
    levy_revenue = levy_eligible_lb * state.market.levy_rate
    voluntary = sum(d.marketing_contribution for d in decisions)
    total_marketing = levy_revenue + voluntary
    state.market.spend_marketing(total_marketing)
    state.market.decay_marketing()
    report.marketing_spend = total_marketing

    # Step 7: clear the market
    price = state.market.clear(total_supply_million)
    report.price = price

    # Step 8: settle each orchard
    for o in state.orchards:
        if o.bankrupt:
            continue
        o.settle(state.year, price, state.market.levy_rate)
        if o.bankrupt:
            report.bankruptcies.append(o.name)

    # Step 9: record + advance
    state.market.record(state.year, total_marketing, new_plantings_total)
    for o in state.orchards:
        report.orchard_lines.append(o.status_line(state.year))
    state.year += 1
    return report


def run_years(state: GameState, n: int,
              decision_fn: Optional[Callable[[GameState], Decision]] = None) -> List[TurnReport]:
    """Run n turns. If `decision_fn` is provided, it's called each turn to
    get the player's decision; otherwise NPC logic is used for the player too.
    """
    reports = []
    for _ in range(n):
        pd = decision_fn(state) if (decision_fn and state.player_index is not None) else None
        reports.append(run_turn(state, player_decision=pd))
    return reports
