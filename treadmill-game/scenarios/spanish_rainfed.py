"""Scenario: Spanish rainfed almonds at the margin.

Demonstrates Reisman's counter-case (p. 8-12): rainfed Spanish almonds
operating as a "crop of last resort," resilient to price crashes precisely
because the system has so little exposure to debt and intensive inputs.
The orchard's earnings are modest, but it survives every shock that breaks
the California archetypes.

Run with:  python -m scenarios.spanish_rainfed
"""

from __future__ import annotations

import random

from game.archetypes import (
    CALIFORNIA_INTENSIVE,
    INVESTOR_MEGAPLANTING,
    SPANISH_RAINFED,
    make_orchard,
)
from game.engine import run_turn, setup_game, update_market_projection
from game.events import (
    EventSchedule,
    drought_event,
    frost_event,
    varroa_mite_event,
)


def main() -> None:
    rng = random.Random(1986)
    schedule = EventSchedule(
        fixed={
            5: [drought_event(severity=0.8)],
            8: [frost_event()],
            12: [varroa_mite_event()],
            18: [drought_event(severity=1.2)],  # devastating multi-year
        },
        stochastic_rate=0.20,
        rng=rng,
    )
    state = setup_game(
        archetypes=[CALIFORNIA_INTENSIVE, INVESTOR_MEGAPLANTING],
        player_archetype=SPANISH_RAINFED,
        schedule=schedule,
        player_name="Spanish smallholder",
    )

    initial_supply = sum(o.produce(0) for o in state.orchards) / 1_000_000
    state.market.clear(initial_supply)
    update_market_projection(state)

    print(f"{'Yr':>3} {'Price':>7} {'Supply':>9} {'Profit_Sm':>11} {'Cap_Sm':>11} {'Cap_Cal':>13} {'Cap_Inv':>15}  Events")
    for _ in range(25):
        report = run_turn(state)
        smallholder = state.player_orchard()
        cal = state.orchards[0]   # CALIFORNIA_INTENSIVE
        inv = state.orchards[1]   # INVESTOR_MEGAPLANTING
        events = "; ".join(e.split(":", 1)[0] for e in report.fired_events)
        # Approximate per-year smallholder profit by tracking running cap delta
        if not hasattr(main, "_prev_cap"):
            main._prev_cap = smallholder.capital - 0  # initial
            yearly_profit = 0.0
        else:
            yearly_profit = smallholder.capital - main._prev_cap
            main._prev_cap = smallholder.capital
        print(f"{report.year-1:>3} "
              f"${report.price:>5.2f} "
              f"{report.total_supply_million_lb:>9,.0f} "
              f"${yearly_profit:>+10,.0f} "
              f"${smallholder.capital:>10,.0f} "
              f"${cal.capital:>12,.0f} "
              f"${inv.capital:>14,.0f}  "
              f"{events}")

    print()
    print("Note: the Spanish smallholder rarely tops the leaderboard, but rarely")
    print("falls off it either. Reisman's point (p. 9): marginality is also a")
    print("kind of resilience.")


if __name__ == "__main__":
    main()
