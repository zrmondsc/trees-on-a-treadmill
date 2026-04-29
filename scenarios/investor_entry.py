"""Scenario: an investor megaplanting joins a saturated market.

Reisman p. 12: "Suddenly almonds were no longer a crop of convenience for
rural households squeaking by but instead the darling of investment groups,
irrigated districts plagued by sinking commodity prices, and industrial-scale
agribusinesses."

This scenario starts from a roughly balanced market and then injects a
giant-capital corporate planting a few years in. The point is to watch how
even one investor-class entrant amplifies the boom-bust cycle for everyone
else, including the small grower who didn't expand.

Run with:  python -m scenarios.investor_entry
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
from game.events import EventSchedule
from game.orchard import Intensification


def main() -> None:
    rng = random.Random(2014)
    schedule = EventSchedule(stochastic_rate=0.10, rng=rng)
    # Start without the investor
    state = setup_game(
        archetypes=[SPANISH_RAINFED, CALIFORNIA_INTENSIVE],
        player_archetype=CALIFORNIA_INTENSIVE,
        schedule=schedule,
        player_name="Mid-size California grower",
    )
    initial_supply = sum(o.produce(0) for o in state.orchards) / 1_000_000
    state.market.clear(initial_supply)
    update_market_projection(state)

    print(f"{'Yr':>3} {'Price':>7} {'Supply':>10} {'5yProj':>9} {'PlayerCap':>13}  Note")
    for _ in range(8):
        report = run_turn(state)
        m = state.market
        print(f"{report.year-1:>3} ${report.price:>5.2f} "
              f"{report.total_supply_million_lb:>9,.0f} "
              f"{m.projected_supply_growth_5yr():>+8.1%} "
              f"${state.player_orchard().capital:>12,.0f}  pre-investor")

    # Year 8: enter the investor
    print()
    print(">>> Year 8: an investment group plants a 600-acre superintensive orchard.")
    print(">>> (Reisman p. 12: 'the darling of investment groups'.)")
    investor = make_orchard(INVESTOR_MEGAPLANTING)
    state.orchards.append(investor)
    state.archetypes.append(INVESTOR_MEGAPLANTING)
    update_market_projection(state)

    for _ in range(20):
        report = run_turn(state)
        m = state.market
        note = ""
        if state.player_orchard().bankrupt:
            note = "PLAYER BANKRUPT"
        print(f"{report.year-1:>3} ${report.price:>5.2f} "
              f"{report.total_supply_million_lb:>9,.0f} "
              f"{m.projected_supply_growth_5yr():>+8.1%} "
              f"${state.player_orchard().capital:>12,.0f}  {note}")

    print()
    for o in state.orchards:
        print(f"  {o.status_line(state.year)}")
        print(f"     cumulative profit: ${o.cumulative_profit:>14,.0f}")


if __name__ == "__main__":
    main()
