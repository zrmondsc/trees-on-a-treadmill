// Behavior tests for the JS port. Mirrors tests/test_loop.py and
// tests/test_market.py. Run with: node web/test_sim.js
//
// These exist to guarantee the browser game and the Python CLI produce the
// same dynamics. If they diverge, the Python tests catch it on one side and
// these catch it on the other.

const fs = require('fs');
const path = require('path');

// Load only the simulation portion (everything before the UI section)
const src = fs.readFileSync(path.join(__dirname, 'game.js'), 'utf-8');
const headerEnd = src.indexOf('// ---- UI');
const cleaned = src.slice(0, headerEnd).replace(/^\s*'use strict'\s*;?/m, '');
// Append code that re-exports the const/let bindings onto globalThis so the
// rest of this file can see them. Functions hoist into eval's scope, but
// const/let do not, so we need this trampoline.
const exposeSymbols = `
;(function() {
  globalThis.REGIME = REGIME;
  globalThis.EVENTS = EVENTS;
  globalThis.ARCHETYPES = ARCHETYPES;
  globalThis.ESTABLISHMENT_COST = ESTABLISHMENT_COST;
  globalThis.BASE_YIELD = BASE_YIELD;
  globalThis.BASE_COST = BASE_COST;
  globalThis.REFERENCE_PRICE = REFERENCE_PRICE;
  globalThis.BASELINE_DEMAND = BASELINE_DEMAND;
  globalThis.DEFAULT_STARTING_TREE_AGE = DEFAULT_STARTING_TREE_AGE;
})();
`;
eval(cleaned + exposeSymbols);

let pass = 0, fail = 0;
function test(name, fn) {
  try {
    fn();
    console.log(`  ✓  ${name}`);
    pass++;
  } catch (e) {
    console.log(`  ✗  ${name}`);
    console.log(`     ${e.message}`);
    if (e.stack) console.log(`     ${e.stack.split('\n').slice(1, 3).join('\n     ')}`);
    fail++;
  }
}
function assert(cond, msg) { if (!cond) throw new Error(msg || 'assertion failed'); }
function assertClose(a, b, eps, msg) {
  if (Math.abs(a - b) > (eps || 1e-6)) throw new Error(`${msg || 'not close'}: ${a} vs ${b}`);
}

// --- Helper: deterministic quiet game ---
function quietGame(playerArchKey = 'intensive') {
  const game = makeGame({ playerArchKey });
  // Replace stochastic events with no-op by neutralizing the rng path:
  // we keep the rng but call eventsForYear only via runTurn which already
  // uses it. To be deterministic across runs we re-seed:
  game.rng = mulberry32(12345);
  // Erase the fixed schedule so quiet means quiet
  game.schedule = {};
  let supply = 0;
  for (const o of game.orchards) supply += orchardProduce(o, 0);
  marketClear(game.market, supply / 1_000_000);
  updateMarketProjection(game);
  return game;
}

console.log('Market unit tests:');

test('clearing at baseline yields reference price', () => {
  const m = makeMarket();
  const p = marketClear(m, m.baselineDemand);
  assertClose(p, m.referencePrice, 0.01, 'price at baseline');
});

test('oversupply drops price below reference', () => {
  const m = makeMarket();
  marketClear(m, m.baselineDemand);
  const balanced = m.currentPrice;
  marketClear(m, m.baselineDemand * 2);
  assert(m.currentPrice < balanced, 'price should fall when supply doubles');
  assert(m.currentPrice < balanced / 2, 'inelastic demand should give >50% price cut');
});

test('marketing lifts price for same supply', () => {
  const m = makeMarket();
  marketClear(m, m.baselineDemand);
  const before = m.currentPrice;
  marketSpendMarketing(m, 1_000_000);
  marketClear(m, m.baselineDemand);
  assert(m.currentPrice > before, 'marketing should raise price');
});

test('marketing efficiency saturates with cumulative spend', () => {
  const m = makeMarket();
  const e0 = m.marketingEfficiency;
  marketSpendMarketing(m, 15_000_000);
  assert(m.marketingEfficiency < 0.5, `efficiency should halve by $5M cumulative; got ${m.marketingEfficiency}`);
  assert(m.marketingEfficiency < e0);
});

test('projection growth signed correctly', () => {
  const m = makeMarket();
  const proj = [1000, 1000, 1000, 1000, 1000, 1500, 1500, 1500, 1500, 1500, 1500];
  marketUpdateProjection(m, proj);
  assertClose(marketProjectedSupplyGrowth5yr(m), 0.5, 1e-6);
});

console.log('\nLoop behavior tests:');

test('long run shows boom-and-crash cycle (price falls below early avg)', () => {
  const game = quietGame();
  const prices = [];
  for (let i = 0; i < 40; i++) {
    runTurn(game, null);
    prices.push(game.market.history.prices[game.market.history.prices.length - 1]);
  }
  const earlyAvg = prices.slice(0, 5).reduce((a, b) => a + b, 0) / 5;
  const minLate = Math.min(...prices.slice(10));
  assert(minLate < earlyAvg, `minimum late price ${minLate.toFixed(2)} should fall below early avg ${earlyAvg.toFixed(2)}`);
});

test('industry acres grow over the long run', () => {
  const game = quietGame();
  const initial = game.orchards.reduce((s, o) => s + orchardTotalAcres(o), 0);
  for (let i = 0; i < 25; i++) runTurn(game, null);
  const final = game.orchards.reduce((s, o) => s + orchardTotalAcres(o), 0);
  assert(final > initial, `acres should grow: ${initial} -> ${final}`);
});

test('Spanish smallholder survives a quiet 25-year run', () => {
  const game = quietGame();
  for (let i = 0; i < 25; i++) runTurn(game, null);
  const smallholder = game.orchards.find(o => o.name === 'Spanish rainfed smallholder');
  assert(!smallholder.bankrupt, 'smallholder should not bankrupt in a quiet run');
});

test('drought hits intensive yields, leaves rainfed alone', () => {
  const game = quietGame();
  const rainfed = game.orchards.find(o => o.name.includes('rainfed'));
  const intensive = game.orchards.find(o => o.name.includes('intensive'));
  const rainfedBefore = orchardProduce(rainfed, 0);
  const intensiveBefore = orchardProduce(intensive, 0);
  EVENTS.drought(1.0).apply(game.market, game.orchards, 0);
  assert(orchardProduce(rainfed, 0) === rainfedBefore, 'rainfed yield should be unchanged');
  assert(orchardProduce(intensive, 0) < intensiveBefore, 'intensive yield should drop');
});

test('varroa hits orchards without self-compatible varieties only', () => {
  const game = quietGame();
  const intensiveNonCompat = game.orchards.find(o => o.name.includes('intensive'));
  const intensiveCompat = makeOrchardFromArchetype('intensive');
  intensiveCompat.usesSelfCompatibleVariety = true;
  game.orchards.push(intensiveCompat);
  const beforeNon = intensiveNonCompat.capital;
  const beforeCompat = intensiveCompat.capital;
  EVENTS.varroa().apply(game.market, game.orchards, 0);
  assert(intensiveNonCompat.capital < beforeNon, 'non-self-compatible orchard should pay');
  assert(intensiveCompat.capital === beforeCompat, 'self-compatible orchard should not pay');
});

test('anticipation: high-anticipation archetype refuses to plant when glut projected', () => {
  const m = makeMarket();
  marketClear(m, m.baselineDemand);
  // Simulate forecast: industry will grow 70% in 5 years
  marketUpdateProjection(m, [1000, 1000, 1000, 1100, 1300, 1700, 1700, 1700, 1700, 1700, 1700]);
  const o = makeOrchard({ name: 't', capital: 2_000_000, anticipationWeight: 0.5, usesSelfCompatible: false });
  o.cohorts.push(makeCohort(-10, 200, REGIME.INTENSIVE));
  const intensiveDecision = decideCaliforniaIntensive(0, m, o);
  assert(intensiveDecision.plantAcres === 0, 'high-anticipation grower should not plant under glut forecast');
});

test('superintensive carries higher establishment cost than intensive', () => {
  assert(ESTABLISHMENT_COST[REGIME.SUPERINTENSIVE] > ESTABLISHMENT_COST[REGIME.INTENSIVE]);
  assert(ESTABLISHMENT_COST[REGIME.INTENSIVE] > ESTABLISHMENT_COST[REGIME.RAINFED]);
});

test('salt accumulates only for non-rainfed bearing acres', () => {
  const rainfedOnly = makeOrchardFromArchetype('rainfed');
  rainfedOnly.cohorts[0].plantingYear = -10; // already mature
  for (let y = 0; y < 5; y++) orchardSettle(rainfedOnly, y, 2.5, 0.03);
  assert(rainfedOnly.saltBurden === 0, 'rainfed should not accumulate salt');

  const intensive = makeOrchardFromArchetype('intensive');
  intensive.cohorts[0].plantingYear = -10;
  for (let y = 0; y < 5; y++) orchardSettle(intensive, y, 2.5, 0.03);
  assert(intensive.saltBurden > 0, 'intensive should accumulate salt');
});

console.log(`\n${pass} passed, ${fail} failed`);
process.exit(fail > 0 ? 1 : 0);
