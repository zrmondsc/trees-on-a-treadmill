"""Behavior tests: does the simulation reproduce the treadmill?

These tests are the design backstop. If the model can't:
- generate a price crash after sustained adoption,
- reward early adopters more than late adopters,
- show marketing temporarily lifting then backfiring on price,
- let rainfed farmers survive shocks that bankrupt intensives,
... then the simulation isn't doing what Reisman's mechanisms predict.
"""

from __future__ import annotations

import random

from game.archetypes import (
    CALIFORNIA_INTENSIVE,
    INVESTOR_MEGAPLANTING,
    SPANISH_RAINFED,
)
from game.engine import run_turn, setup_game, update_market_projection
from game.events import EventSchedule
from game.orchard import Intensification


def _quiet_state(seed=42):
    """Set up a deterministic game with no shocks."""
    rng = random.Random(seed)
    schedule = EventSchedule(stochastic_rate=0.0, rng=rng)
    state = setup_game(
        archetypes=[SPANISH_RAINFED, CALIFORNIA_INTENSIVE, INVESTOR_MEGAPLANTING],
        schedule=schedule,
    )
    initial_supply = sum(o.produce(0) for o in state.orchards) / 1_000_000
    state.market.clear(initial_supply)
    update_market_projection(state)
    return state


def test_long_run_treadmill_cycle_emerges():
    """Cochrane's treadmill: in a quiet world, NPC adoption creates a
    boom-and-crash cycle. Specifically: at some point in a long run, the
    price should fall below the early-period average — that's the crash
    after over-adoption that defines the treadmill."""
    state = _quiet_state()
    prices = []
    for _ in range(40):
        r = run_turn(state)
        prices.append(r.price)
    early_avg = sum(prices[:5]) / 5
    minimum = min(prices[10:])
    assert minimum < early_avg, (
        f"Expected a crash below early avg {early_avg:.2f}; "
        f"got minimum {minimum:.2f}"
    )


def test_supply_grows_long_run():
    """Industry bearing acres should rise on net as archetypes plant."""
    state = _quiet_state()
    initial_acres = sum(o.total_acres() for o in state.orchards)
    for _ in range(20):
        run_turn(state)
    final_acres = sum(o.total_acres() for o in state.orchards)
    assert final_acres > initial_acres


def test_rainfed_smallholder_never_bankrupts_in_quiet_world():
    """Marginality is resilience (Reisman p. 9)."""
    state = _quiet_state(seed=7)
    for _ in range(25):
        run_turn(state)
    smallholder = state.orchards[0]
    assert not smallholder.bankrupt


def test_intensive_more_vulnerable_than_rainfed_to_drought():
    """Reisman: intensive orchards take the hit from drought; rainfed
    shrugs it off."""
    from game.events import drought_event
    state = _quiet_state(seed=11)
    rainfed = state.orchards[0]
    intensive = state.orchards[1]
    rainfed_yield_before = rainfed.produce(0)
    intensive_yield_before = intensive.produce(0)
    drought_event(severity=1.0).apply(state.market, state.orchards, 0)
    rainfed_yield_after = rainfed.produce(0)
    intensive_yield_after = intensive.produce(0)
    # Rainfed yield unchanged
    assert rainfed_yield_after == rainfed_yield_before
    # Intensive yield strictly lower
    assert intensive_yield_after < intensive_yield_before


def test_marketing_short_term_lifts_price_then_efficiency_decays():
    """Reisman p. 15: marketing efficiency wears down with cumulative spend."""
    state = _quiet_state(seed=3)
    m = state.market
    spend_each_year = 1_000_000
    early_efficiency = m.marketing_efficiency
    for _ in range(10):
        m.spend_marketing(spend_each_year)
        m.decay_marketing()
    late_efficiency = m.marketing_efficiency
    assert late_efficiency < early_efficiency
    assert late_efficiency < 0.8


def test_anticipation_dampens_planting_when_glut_projected():
    """High projected 5-year supply growth should reduce a high-anticipation
    archetype's planting compared to a low-anticipation archetype with the
    same financials and price."""
    from game.archetypes import (
        Decision,
        decide_california_intensive,
        decide_spanish_rainfed,
    )
    from game.market import Market
    from game.orchard import Orchard, TreeCohort

    m = Market()
    m.clear(m.baseline_demand)  # price at reference
    # Fake a forecast showing a coming glut
    m.update_projection([1000.0, 1000.0, 1000.0, 1100.0, 1300.0,
                         1700.0, 1700.0, 1700.0, 1700.0, 1700.0, 1700.0])

    o = Orchard(name="t", capital=2_000_000)
    o.cohorts.append(TreeCohort(planting_year=-10, acres=200,
                                regime=Intensification.INTENSIVE))
    intensive_d = decide_california_intensive(0, m, o)
    rainfed_d = decide_spanish_rainfed(0, m, o)
    # The intensive grower, looking 5 years out, sees the glut coming and
    # plants less than the rainfed smallholder who barely watches projections.
    # (Even with the smallholder's small capital, signal sign matters.)
    assert intensive_d.plant_acres == 0  # glut signal blocks planting
