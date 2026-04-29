"""Interactive command-line interface.

The player runs an orchard alongside three NPC archetypes for 25 years.
Each year they see the market state, the forward-looking nursery-sale
projection (the anticipatory mechanism, Reisman p. 14), and a menu of choices.

The point of this interface is pedagogy. Phrasing matches the book where
possible — players should leave with the vocabulary, not just a score.
"""

from __future__ import annotations

import argparse
import random
import sys
from typing import Optional

from .archetypes import (
    CALIFORNIA_INTENSIVE,
    INVESTOR_MEGAPLANTING,
    SPANISH_RAINFED,
    Decision,
)
from .engine import GameState, run_turn, setup_game, update_market_projection
from .events import EventSchedule, aha_endorsement_event, china_export_boom_event, panic_levy_increase_event
from .orchard import Intensification


# ---- Display helpers --------------------------------------------------------

def banner(text: str) -> None:
    print()
    print("=" * 72)
    print(f"  {text}")
    print("=" * 72)


def render_market_snapshot(state: GameState) -> None:
    m = state.market
    growth = m.projected_supply_growth_5yr()
    print()
    print(f"Year {state.year}.")
    print(f"  Spot price:                     ${m.current_price:5.2f} / lb")
    print(f"  Reference price (Y0 baseline):  ${m.reference_price:5.2f} / lb")
    print(f"  Industry bearing acres now:     {m.projected_bearing_acres[0]:>10,.0f}")
    print(f"  Industry bearing acres 5 yr:    {m.projected_bearing_acres[5]:>10,.0f}")
    print(f"  Projected 5-yr supply growth:   {growth:>+10.1%}  "
          f"<-- nursery-sale data, the Almond Board's forward look (Reisman p. 14)")
    print(f"  Marketing levy:                 ${m.levy_rate:5.3f} / lb")
    print(f"  Marketing demand lift:          {m.marketing_demand_lift:>10,.0f}  "
          f"million lb shifted out, efficiency {m.marketing_efficiency:.2f}")


def render_player_status(state: GameState) -> None:
    o = state.player_orchard()
    if o is None:
        return
    by_regime = o.acres_by_regime()
    print()
    print(f"YOUR FARM ({o.name}):")
    print(f"  Capital:               ${o.capital:>12,.0f}")
    print(f"  Total acres:           {o.total_acres():>12,.0f}")
    print(f"  Bearing acres:         {o.bearing_acres(state.year):>12,.0f}")
    print(f"  Rainfed acres:         {by_regime[Intensification.RAINFED]:>12,.0f}")
    print(f"  Intensive acres:       {by_regime[Intensification.INTENSIVE]:>12,.0f}")
    print(f"  Superintensive acres:  {by_regime[Intensification.SUPERINTENSIVE]:>12,.0f}")
    print(f"  Salt burden (0-1):     {o.salt_burden:>12.2f}  "
          f"(Reisman ch. 2: requires leaching fraction)")
    print(f"  Pesticide dependency:  {o.pesticide_dependency:>12.2f}")
    print(f"  Self-compatible variety (Spanish Guara line): {o.uses_self_compatible_variety}")


def render_world(state: GameState) -> None:
    print()
    print("THE FIELD:")
    for o in state.orchards:
        marker = "  YOU >>" if o is state.player_orchard() else "       "
        print(f"{marker} {o.status_line(state.year)}")


# ---- Decision menu ----------------------------------------------------------

PLANTING_REGIMES = {
    "1": (Intensification.RAINFED, "Rainfed (Spanish-style; low yield, low cost, resilient)"),
    "2": (Intensification.INTENSIVE, "Intensive (California-style drip irrigation, agrichemicals, trucked bees)"),
    "3": (Intensification.SUPERINTENSIVE, "Superintensive hedgerow (highest yield, highest debt, highest salt)"),
}


def ask_int(prompt: str, lo: int = 0, hi: int = 10**9, default: int = 0) -> int:
    while True:
        raw = input(f"{prompt} [default {default}]: ").strip()
        if raw == "":
            return default
        try:
            v = int(raw)
            if lo <= v <= hi:
                return v
        except ValueError:
            pass
        print(f"  Please enter an integer between {lo} and {hi}.")


def ask_choice(prompt: str, choices: dict, default: Optional[str] = None) -> str:
    print(prompt)
    for key, (_, label) in choices.items():
        print(f"  [{key}] {label}")
    while True:
        raw = input(f"Pick {'/'.join(choices.keys())} [default {default}]: ").strip()
        if raw == "" and default is not None:
            return default
        if raw in choices:
            return raw


def get_player_decision(state: GameState) -> Decision:
    print()
    print("YOUR MOVE.")
    o = state.player_orchard()
    assert o is not None

    plant_acres = ask_int("How many acres to plant this year?", lo=0, hi=2000, default=0)
    regime = Intensification.RAINFED
    if plant_acres > 0:
        key = ask_choice("Choose a planting regime:", PLANTING_REGIMES, default="2")
        regime, _ = PLANTING_REGIMES[key]
    remove_acres = ask_int("How many acres to remove (push out trees)?",
                           lo=0, hi=int(o.total_acres()), default=0)
    voluntary = ask_int("Voluntary marketing contribution above the levy ($)?",
                        lo=0, hi=int(max(0, o.capital)), default=0)
    switch = False
    if not o.uses_self_compatible_variety and o.capital > 50_000:
        print()
        print("Switch to self-compatible varieties (Spanish Guara line, est. 1986)?")
        print("This avoids honeybee rental costs but costs $50,000 to convert and reduces")
        print("yields by 10% on existing cohorts (replanting required for new ones).")
        ans = input("(y/N): ").strip().lower()
        if ans == "y":
            switch = True
            o.capital -= 50_000  # one-time conversion cost

    return Decision(
        plant_acres=plant_acres,
        plant_regime=regime,
        remove_acres=remove_acres,
        marketing_contribution=voluntary,
        switch_to_self_compatible=switch,
    )


# ---- Main loop --------------------------------------------------------------

def play(years: int = 25, seed: Optional[int] = None, player_archetype_key: str = "intensive") -> None:
    arch_lookup = {
        "rainfed": SPANISH_RAINFED,
        "intensive": CALIFORNIA_INTENSIVE,
        "investor": INVESTOR_MEGAPLANTING,
    }
    player_arch = arch_lookup.get(player_archetype_key, CALIFORNIA_INTENSIVE)

    rng = random.Random(seed)
    schedule = EventSchedule(
        fixed={
            3: [aha_endorsement_event()],
            10: [china_export_boom_event()],
            16: [panic_levy_increase_event()],
        },
        stochastic_rate=0.25,
        rng=rng,
    )

    state = setup_game(
        archetypes=[SPANISH_RAINFED, CALIFORNIA_INTENSIVE, INVESTOR_MEGAPLANTING],
        player_archetype=player_arch,
        schedule=schedule,
        player_name="You",
    )
    # Initialize price so the first year has a sensible signal
    initial_supply = sum(o.produce(0) for o in state.orchards) / 1_000_000
    state.market.clear(initial_supply)
    update_market_projection(state)

    banner("Trees on a Treadmill")
    print("Based on Emily Reisman, The Almond Paradox (UC Press, 2025).")
    print()
    print("You're starting an almond orchard. Three NPC archetypes share the market.")
    print("Each year, the price will tell you whether to plant, hold, or pull out.")
    print("But the price is downstream of decisions made by everyone — including you,")
    print("five years ago. Watch the projected 5-year supply growth: that's the same")
    print("nursery-sale forecast the Almond Board uses to panic.")

    for _ in range(years):
        render_market_snapshot(state)
        render_world(state)
        render_player_status(state)
        if state.player_orchard().bankrupt:
            banner("You went bankrupt.")
            print("The treadmill caught up. Cochrane's third option for laggards: exit.")
            break
        decision = get_player_decision(state)
        report = run_turn(state, player_decision=decision)
        print()
        print(f"-- Year {report.year} resolved --")
        for ev in report.fired_events:
            print(f"  EVENT: {ev}")
        if report.bankruptcies:
            for name in report.bankruptcies:
                print(f"  BANKRUPTCY: {name}")
        print(f"  New plantings industry-wide: {report.new_plantings_acres:,.0f} acres")
        print(f"  Total marketing spend:        ${report.marketing_spend:,.0f}")

    banner("Game over")
    o = state.player_orchard()
    print(f"Final capital:           ${o.capital:>12,.0f}")
    print(f"Cumulative profit:       ${o.cumulative_profit:>12,.0f}")
    print(f"Final acres:             {o.total_acres():>12,.0f}")
    print(f"Bankrupt:                {o.bankrupt}")
    print()
    print("There is no win condition. That's the point. The treadmill structures")
    print("the field of play. You can survive it, get rich and crash, or stay small")
    print("at the margin. None of these are failures of will — they are the shape")
    print("of agrarian capitalism Reisman is mapping.")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Trees on a Treadmill — interactive game.")
    parser.add_argument("--years", type=int, default=25)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--archetype", choices=["rainfed", "intensive", "investor"],
                        default="intensive",
                        help="Which farmer archetype to play.")
    args = parser.parse_args(argv)
    play(years=args.years, seed=args.seed, player_archetype_key=args.archetype)
    return 0


if __name__ == "__main__":
    sys.exit(main())
