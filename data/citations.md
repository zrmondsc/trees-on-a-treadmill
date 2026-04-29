# Citations

Each game mechanic below is tied to specific pages in Reisman, *The Almond
Paradox* (UC Press, 2025). Page numbers refer to the book's print edition.

## Cochrane's loop (game/market.py, game/orchard.py)

- **p. 14**: "The technological treadmill, as theorized by Willard Cochrane,
  explains that farmers are effectively compelled to adopt new practices by
  falling prices."
- **p. 14**: A laggard "can either increase their yields with new technology,
  scale up their operation, or risk going out of business." → modeled as the
  three available laggard responses each turn.

## Anticipatory adoption (game/orchard.py, game/engine.py)

- **p. 14**: "Almonds, and likely other permanent crops like vines and other
  trees, exhibit hypersensitivity to the risk of a price fall, even if it
  never occurs." → `anticipation_weight` parameter on each archetype.
- **p. 14**: "The Almond Board of California keeps careful measurements of new
  plantings and nursery sales in order to estimate production three, five, and
  ten years down the road." → `Market.future_supply_projection()` exposes the
  same forward look to the player.
- **p. 15**: "Permanent crops get on the treadmill even when their present
  circumstances seem rosy." → in scenarios where current price is high,
  archetypes still adopt if projected supply growth is high.

## Marketing as collective technology (game/market.py, game/inputs.py)

- **p. 15**: "I see marketing as a technology, just like agrichemicals or
  machinery, upon which almond growers became dependent."
- **p. 15**: "The Almond Board of California is highly effective because, like
  other federal marketing orders, it has the force of law to collect its dues,
  overcoming a collective action problem among growers." → marketing levy is
  collected from all California-archetype orchards, not voluntary.
- **p. 15**: "These investments in boosting demand tend to ratchet up over time
  as existing markets become saturated and attracting new customers becomes
  more costly." → `Market.marketing_efficiency` decays with cumulative spend.
- **p. 15-16**: "Marketing is thus an inherently imprecise tool in the
  technological treadmill that can backfire spectacularly." → high prices from
  marketing-led demand attract new growers, who plant, who later flood supply.
- **p. 7**: "By 2016 the Almond Board was so panicked about the increase in
  plantings that it sought approval from the USDA to increase the assessment
  by 33 percent." → encoded as a "panic levy increase" event.

## Input lock-in (game/inputs.py)

- **Ch. 2 (irrigation, pp. 65-66)**: salt buildup from intensive irrigation
  requires a 15-30% leaching fraction. → `Orchard.salt_burden` and
  `leaching_fraction`.
- **Ch. 3 (pollination, pp. 76-92)**: California almonds depend on trucked-in
  honeybees; Spanish self-compatible varieties (Guara, 1986) reduce that
  dependence. → variety choice affects pollination cost.
- **Ch. 1 (breeding)**: thin-shell Nonpareil deepened insecticide dependence.
  → variety choice affects pest pressure.

## Marginality and the Spanish case (scenarios/spanish_rainfed.py)

- **p. 8-9**: "Almonds are what you grow where you can't grow anything else."
  Rainfed almonds as marginal companion to wheat, vines, olives.
- **p. 11-12**: 1989 EU subsidy law; intensive irrigated orchards become
  Spain's production majority by 2022. → captured as the investor-entry event
  in `scenarios/investor_entry.py`.
