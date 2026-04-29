"""Unit tests for the market clearing mechanism."""

from game.market import DEFAULT_BASELINE_DEMAND, DEFAULT_REFERENCE_PRICE, Market


def test_clearing_at_baseline_yields_reference_price():
    m = Market()
    price = m.clear(DEFAULT_BASELINE_DEMAND)
    assert abs(price - DEFAULT_REFERENCE_PRICE) < 0.01


def test_oversupply_drops_price():
    m = Market()
    p_balanced = m.clear(DEFAULT_BASELINE_DEMAND)
    p_glut = m.clear(DEFAULT_BASELINE_DEMAND * 2)
    assert p_glut < p_balanced
    # With elasticity = 0.6, doubling supply roughly cuts price by 2^(1/0.6) ~ 3.2x
    assert p_glut < p_balanced / 2


def test_marketing_lifts_demand():
    m = Market()
    m.clear(DEFAULT_BASELINE_DEMAND)
    p0 = m.current_price
    m.spend_marketing(50_000_000)
    m.clear(DEFAULT_BASELINE_DEMAND)
    p1 = m.current_price
    assert p1 > p0  # same supply, higher demand → higher price


def test_marketing_efficiency_decays():
    m = Market()
    e0 = m.marketing_efficiency
    m.spend_marketing(15_000_000)
    e1 = m.marketing_efficiency
    assert e1 < e0
    assert e1 < 0.5  # halves around $5M cumulative


def test_projection_growth_is_signed():
    m = Market()
    # Industry has 1000 bearing acres now and 1500 in 5 years
    proj = [1000.0] * 5 + [1500.0] + [1500.0] * 5
    m.update_projection(proj)
    assert abs(m.projected_supply_growth_5yr() - 0.5) < 1e-6
