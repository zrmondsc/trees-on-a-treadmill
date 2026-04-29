"""Scenario: the California almond boom and crash, 2000-2025.

Replays Reisman's narrative arc (Introduction, pp. 7-8): rising demand from
marketing through the late 1990s; AHA endorsement and product proliferation
in the early 2000s; surging plantings drawn in by consistently high prices;
2014-16 drought, with prices hitting record highs even as production stays
strong; 2016 panic levy increase; growing pile of new plantings finally
overwhelms demand; prices fall by half by 2023.

Run with:  python -m scenarios.california_2000s
"""

from __future__ import annotations

import random

from game.archetypes import CALIFORNIA_INTENSIVE, INVESTOR_MEGAPLANTING, SPANISH_RAINFED
from game.engine import run_turn, setup_game, update_market_projection
from game.events import (
    EventSchedule,
    aha_endorsement_event,
    china_export_boom_event,
    drought_event,
    panic_levy_increase_event,
    varroa_mite_event,
)


def main() -> None:
    rng = random.Random(1994)
    schedule = EventSchedule(
        fixed={
            # Year 0 is "the late 1990s" in narrative time
            2: [aha_endorsement_event()],         # Reisman p. 7
            8: [varroa_mite_event()],              # mid-2000s pollinator pressure
            10: [china_export_boom_event()],       # Almond Board's Asian push
            14: [drought_event(severity=0.8)],     # 2014-16 drought
            15: [drought_event(severity=0.8)],
            16: [panic_levy_increase_event()],     # USDA approves 33% levy raise
        },
        stochastic_rate=0.10,
        rng=rng,
    )
    state = setup_game(
        archetypes=[SPANISH_RAINFED, CALIFORNIA_INTENSIVE, INVESTOR_MEGAPLANTING],
        player_archetype=None,  # headless
        schedule=schedule,
    )
    # Prime initial market clearing
    initial_supply = sum(o.produce(0) for o in state.orchards) / 1_000_000
    state.market.clear(initial_supply)
    update_market_projection(state)

    print(f"{'Yr':>3} {'Price':>7} {'Supply':>9} {'Demand':>9} {'5yProj':>9} {'Mktg':>11} {'NewAcres':>10}  Events")
    for _ in range(28):
        report = run_turn(state)
        events = "; ".join(e.split(":", 1)[0] for e in report.fired_events)
        m = state.market
        print(f"{report.year-1:>3} "
              f"${report.price:>5.2f} "
              f"{report.total_supply_million_lb:>9,.0f} "
              f"{m.current_demand:>9,.0f} "
              f"{m.projected_supply_growth_5yr():>+8.1%} "
              f"${report.marketing_spend:>9,.0f} "
              f"{report.new_plantings_acres:>10,.0f}  "
              f"{events}")

    print()
    print("Outcomes (final state):")
    for o in state.orchards:
        print(f"  {o.status_line(state.year)}")
        print(f"     cumulative profit: ${o.cumulative_profit:>14,.0f}")


if __name__ == "__main__":
    main()
