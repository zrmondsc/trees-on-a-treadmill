"""Market: industry-level supply, demand, marketing, and price formation.

The market is the heart of the treadmill. Every farmer's individual choices
aggregate here, and the resulting price is what compels the next round of
adoption. The market also exposes a forward look at projected supply (from
nursery sales) — the data point Reisman identifies as a key driver of
anticipatory adoption (p. 14).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


# --- Price formation ----------------------------------------------------------
#
# Demand is downward-sloping in price; marketing shifts the demand curve out.
# Price clears the market by equating supply and demand. We use a constant-
# elasticity demand: Q_d = D0 * (P / P_ref) ** (-elasticity), where D0 is
# baseline demand at the reference price and grows with marketing efficacy.
#
# Inverting: P = P_ref * (Q_supplied / D0) ** (-1/elasticity)
#
# Demand elasticity for nuts is empirically modest (~0.6); below 1 means
# overproduction crashes prices hard.

DEFAULT_REFERENCE_PRICE = 2.50      # USD/lb, vaguely calibrated to early-2000s almonds
DEFAULT_DEMAND_ELASTICITY = 0.6     # |dlnQ/dlnP|, inelastic = treadmill bites
# Baseline demand is calibrated so that the three default-archetype starting
# orchards (~770 acres, mostly intensive) produce roughly enough almonds to
# clear at the reference price. The unit is *millions of pounds*, but the
# scale is internal to the sim — keep all supply numbers in the same units.
DEFAULT_BASELINE_DEMAND = 1.8       # million lb at reference price, year zero


@dataclass
class MarketHistory:
    """Year-by-year record. Useful for plotting, and for archetypes that look
    at trends rather than just spot prices."""
    years: List[int] = field(default_factory=list)
    prices: List[float] = field(default_factory=list)
    supplies: List[float] = field(default_factory=list)
    demands: List[float] = field(default_factory=list)
    marketing_spend: List[float] = field(default_factory=list)
    new_plantings: List[float] = field(default_factory=list)


@dataclass
class Market:
    """Industry-level state and price formation logic.

    Marketing efficacy decays with cumulative spend, encoding Reisman's
    observation (p. 15) that "these investments in boosting demand tend to
    ratchet up over time as existing markets become saturated and attracting
    new customers becomes more costly."
    """

    reference_price: float = DEFAULT_REFERENCE_PRICE
    demand_elasticity: float = DEFAULT_DEMAND_ELASTICITY
    baseline_demand: float = DEFAULT_BASELINE_DEMAND  # million lb

    # Marketing levy state (Almond Board analog)
    levy_rate: float = 0.03           # USD/lb, like the historic 3 cents/lb
    cumulative_marketing_spend: float = 0.0
    marketing_demand_lift: float = 0.0   # current shift to baseline_demand
    marketing_efficiency: float = 1.0    # multiplier on each new dollar of ad spend

    # Forward look — populated each turn from current planting decisions.
    # Index k represents projected industry-wide bearing acres k years out.
    projected_bearing_acres: List[float] = field(default_factory=lambda: [0.0] * 11)

    history: MarketHistory = field(default_factory=MarketHistory)

    # Latest spot values (refreshed by `clear()`)
    current_price: float = DEFAULT_REFERENCE_PRICE
    current_supply: float = 0.0
    current_demand: float = 0.0

    def effective_demand(self) -> float:
        """Baseline demand at reference price, after marketing shifts."""
        return self.baseline_demand + self.marketing_demand_lift

    def clear(self, total_supply_million_lb: float) -> float:
        """Compute the clearing price for a given supply.

        Returns the new price and updates `current_*` and `history`.
        """
        d0 = self.effective_demand()
        if total_supply_million_lb <= 0 or d0 <= 0:
            price = self.reference_price * 2.0  # supply shock; cap at 2x ref
        else:
            ratio = total_supply_million_lb / d0
            # P = P_ref * ratio ** (-1/elasticity)
            price = self.reference_price * (ratio ** (-1.0 / self.demand_elasticity))
            # Soft floor and ceiling so a single bad year doesn't break the sim
            price = max(0.30, min(price, 12.0))

        # Realized demand at this price (constant-elasticity demand curve)
        realized_demand = d0 * (price / self.reference_price) ** (-self.demand_elasticity)

        self.current_price = price
        self.current_supply = total_supply_million_lb
        self.current_demand = realized_demand
        return price

    def spend_marketing(self, dollars: float) -> None:
        """Spend `dollars` on advertising. Demand lift is a concave function
        of spend, with diminishing returns (Reisman p. 15).

        The dollar amount this turn lifts demand permanently (with decay
        applied later via `decay_marketing()`), encoding that the Almond
        Board's campaigns built durable but eroding demand for almonds.
        """
        if dollars <= 0:
            return
        # Diminishing returns: each new dollar buys less demand than the last.
        # 1 million lb of new demand per $1M spent at full efficiency, scaled
        # by current efficiency.
        new_lift = dollars * 1.0e-6 * self.marketing_efficiency
        self.marketing_demand_lift += new_lift
        self.cumulative_marketing_spend += dollars
        # Saturation: efficiency halves every $5M cumulative spend (matched
        # to the rescaled baseline_demand of ~1.8 million lb).
        self.marketing_efficiency = 1.0 / (1.0 + self.cumulative_marketing_spend / 5_000_000)

    def decay_marketing(self, decay_rate: float = 0.08) -> None:
        """Some demand lift erodes naturally each year (forgotten ads,
        consumers churning, competing food trends). Without continued
        spending, the lift shrinks."""
        self.marketing_demand_lift *= (1 - decay_rate)

    # --- Forward look (anticipatory pressure) ---------------------------------

    def update_projection(self, new_bearing_acres_by_horizon: List[float]) -> None:
        """Replace the projected bearing-acres curve.

        Index 0 is "this year"; index 10 is "ten years out." This is the
        equivalent of the Almond Board's 3, 5, and 10-year forecasts that
        Reisman discusses on p. 14.
        """
        if len(new_bearing_acres_by_horizon) != 11:
            raise ValueError("Projection must have 11 horizons (year 0 to year 10).")
        self.projected_bearing_acres = list(new_bearing_acres_by_horizon)

    def projected_supply_growth_5yr(self) -> float:
        """Fractional growth in industry bearing acres over the next 5 years.

        This is the headline number a panicked Almond Board (or a worried
        farmer) would stare at. A value > 0.20 means the industry is
        scheduled for a glut whether anyone wants one or not.
        """
        now = max(self.projected_bearing_acres[0], 1.0)
        future = self.projected_bearing_acres[5]
        return (future - now) / now

    # --- Recording ------------------------------------------------------------

    def record(self, year: int, marketing_spend: float, new_plantings_acres: float) -> None:
        """Append the current spot values to the history."""
        self.history.years.append(year)
        self.history.prices.append(self.current_price)
        self.history.supplies.append(self.current_supply)
        self.history.demands.append(self.current_demand)
        self.history.marketing_spend.append(marketing_spend)
        self.history.new_plantings.append(new_plantings_acres)
