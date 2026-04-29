// =========================================================================
// Trees on a Treadmill — JS port
// Mirrors game/{market,orchard,events,archetypes,engine}.py from the repo.
// All numeric constants are kept identical so the simulation behaves the same
// in the browser as in the Python tests.
// =========================================================================

'use strict';

// ---- Constants -----------------------------------------------------------

const REFERENCE_PRICE = 2.50;
const DEMAND_ELASTICITY = 0.6;
const BASELINE_DEMAND = 1.8;            // million lb at reference price
const ESTABLISHMENT_YEARS = 4;

const REGIME = Object.freeze({
  RAINFED: 'rainfed',
  INTENSIVE: 'intensive',
  SUPERINTENSIVE: 'superintensive',
});

const BASE_YIELD = {
  [REGIME.RAINFED]: 250,
  [REGIME.INTENSIVE]: 2400,
  [REGIME.SUPERINTENSIVE]: 3500,
};

const BASE_COST = {
  [REGIME.RAINFED]: 200,
  [REGIME.INTENSIVE]: 2800,
  [REGIME.SUPERINTENSIVE]: 4500,
};

const ESTABLISHMENT_COST = {
  [REGIME.RAINFED]: 800,
  [REGIME.INTENSIVE]: 9000,
  [REGIME.SUPERINTENSIVE]: 14000,
};

const REGIME_LABEL = {
  [REGIME.RAINFED]: 'Rainfed',
  [REGIME.INTENSIVE]: 'Intensive',
  [REGIME.SUPERINTENSIVE]: 'Superintensive',
};

// ---- Yield curve ---------------------------------------------------------

function yieldFactor(age) {
  if (age < ESTABLISHMENT_YEARS) return 0;
  if (age === 4) return 0.30;
  if (age === 5) return 0.60;
  if (age === 6) return 0.90;
  if (age <= 22) return 1.0;
  return Math.max(0, 1.0 - 0.05 * (age - 22));
}

// ---- Cohort and Orchard --------------------------------------------------

function makeCohort(plantingYear, acres, regime) {
  return { plantingYear, acres, regime };
}

function cohortAge(c, currentYear) { return currentYear - c.plantingYear; }
function cohortIsProductive(c, currentYear) { return yieldFactor(cohortAge(c, currentYear)) > 0; }
function cohortYieldLb(c, currentYear) {
  return c.acres * BASE_YIELD[c.regime] * yieldFactor(cohortAge(c, currentYear));
}

function makeOrchard({ name, capital, anticipationWeight, usesSelfCompatible, isPlayer = false }) {
  return {
    name,
    cohorts: [],
    capital: capital,
    debtThreshold: -500_000,
    saltBurden: 0,
    pesticideDependency: 0,
    usesSelfCompatibleVariety: !!usesSelfCompatible,
    anticipationWeight,
    isPlayer,
    bankrupt: false,
    cumulativeProfit: 0,
    currentYearYieldModifier: 1.0,
    currentYearIntensiveYieldModifier: 1.0,
  };
}

function orchardTotalAcres(o) { return o.cohorts.reduce((s, c) => s + c.acres, 0); }
function orchardBearingAcres(o, year) {
  return o.cohorts.reduce((s, c) => s + (cohortIsProductive(c, year) ? c.acres : 0), 0);
}
function orchardAcresByRegime(o) {
  const by = { [REGIME.RAINFED]: 0, [REGIME.INTENSIVE]: 0, [REGIME.SUPERINTENSIVE]: 0 };
  for (const c of o.cohorts) by[c.regime] += c.acres;
  return by;
}
function orchardDominantRegime(o) {
  const by = orchardAcresByRegime(o);
  const total = orchardTotalAcres(o);
  if (total === 0) return null;
  return Object.entries(by).sort((a,b) => b[1]-a[1])[0][0];
}
function orchardProduce(o, year) {
  let total = 0;
  for (const c of o.cohorts) {
    let y = cohortYieldLb(c, year) * o.currentYearYieldModifier;
    if (c.regime !== REGIME.RAINFED) y *= o.currentYearIntensiveYieldModifier;
    total += y;
  }
  return total;
}
function orchardOperatingCost(o, year) {
  let cost = 0;
  for (const c of o.cohorts) {
    let base = BASE_COST[c.regime] * c.acres;
    if (c.regime !== REGIME.RAINFED) base *= 1.0 + 0.20 * o.saltBurden;
    if (c.regime !== REGIME.RAINFED && !o.usesSelfCompatibleVariety) base += 250 * c.acres;
    cost += base;
  }
  return cost;
}
function orchardPlant(o, year, acres, regime) {
  const cost = ESTABLISHMENT_COST[regime] * acres;
  if (o.capital < cost || acres <= 0) return false;
  o.capital -= cost;
  o.cohorts.push(makeCohort(year, acres, regime));
  return true;
}
function orchardRemove(o, currentYear, acres) {
  // Remove oldest first
  const order = [...o.cohorts].sort((a,b) => a.plantingYear - b.plantingYear);
  let remaining = acres;
  for (const c of order) {
    if (remaining <= 0) break;
    const take = Math.min(c.acres, remaining);
    c.acres -= take;
    remaining -= take;
  }
  o.cohorts = o.cohorts.filter(c => c.acres > 0.001);
  return acres - Math.max(0, remaining);
}
function orchardSettle(o, year, pricePerLb, levyPerLb) {
  const productionLb = orchardProduce(o, year);
  const revenue = productionLb * pricePerLb;
  const costs = orchardOperatingCost(o, year);
  let levyEligibleLb = 0;
  for (const c of o.cohorts) {
    if (c.regime !== REGIME.RAINFED) {
      let y = cohortYieldLb(c, year) * o.currentYearYieldModifier * o.currentYearIntensiveYieldModifier;
      levyEligibleLb += y;
    }
  }
  const levy = levyEligibleLb * levyPerLb;
  const profit = revenue - costs - levy;
  o.capital += profit;
  o.cumulativeProfit += profit;

  let intensiveBearing = 0;
  for (const c of o.cohorts) {
    if (c.regime !== REGIME.RAINFED && cohortIsProductive(c, year)) intensiveBearing += c.acres;
  }
  if (intensiveBearing > 0) {
    o.saltBurden = Math.min(1.0, o.saltBurden + 0.05);
    o.pesticideDependency = Math.min(1.0, o.pesticideDependency + 0.04);
  } else {
    o.saltBurden = Math.max(0, o.saltBurden - 0.02);
    o.pesticideDependency = Math.max(0, o.pesticideDependency - 0.02);
  }

  if (o.capital < o.debtThreshold) o.bankrupt = true;

  o.currentYearYieldModifier = 1.0;
  o.currentYearIntensiveYieldModifier = 1.0;
  return profit;
}

// ---- Market --------------------------------------------------------------

function makeMarket() {
  return {
    referencePrice: REFERENCE_PRICE,
    demandElasticity: DEMAND_ELASTICITY,
    baselineDemand: BASELINE_DEMAND,
    levyRate: 0.03,
    cumulativeMarketingSpend: 0,
    marketingDemandLift: 0,
    marketingEfficiency: 1.0,
    projectedBearingAcres: new Array(11).fill(0),
    currentPrice: REFERENCE_PRICE,
    currentSupply: 0,
    currentDemand: 0,
    history: { years: [], prices: [], supplies: [], demands: [], marketing: [], newPlantings: [], supplyByRegime: [] },
  };
}

function marketEffectiveDemand(m) { return m.baselineDemand + m.marketingDemandLift; }

function marketClear(m, totalSupplyMillionLb) {
  const d0 = marketEffectiveDemand(m);
  let price;
  if (totalSupplyMillionLb <= 0 || d0 <= 0) {
    price = m.referencePrice * 2.0;
  } else {
    const ratio = totalSupplyMillionLb / d0;
    price = m.referencePrice * Math.pow(ratio, -1.0 / m.demandElasticity);
    price = Math.max(0.30, Math.min(price, 12.0));
  }
  const realizedDemand = d0 * Math.pow(price / m.referencePrice, -m.demandElasticity);
  m.currentPrice = price;
  m.currentSupply = totalSupplyMillionLb;
  m.currentDemand = realizedDemand;
  return price;
}

function marketSpendMarketing(m, dollars) {
  if (dollars <= 0) return;
  const newLift = dollars * 1e-6 * m.marketingEfficiency;
  m.marketingDemandLift += newLift;
  m.cumulativeMarketingSpend += dollars;
  m.marketingEfficiency = 1.0 / (1.0 + m.cumulativeMarketingSpend / 5_000_000);
}
function marketDecayMarketing(m, decayRate = 0.08) {
  m.marketingDemandLift *= (1 - decayRate);
}

function marketUpdateProjection(m, proj) { m.projectedBearingAcres = [...proj]; }

function marketProjectedSupplyGrowth5yr(m) {
  const now = Math.max(m.projectedBearingAcres[0], 1);
  const fut = m.projectedBearingAcres[5];
  return (fut - now) / now;
}

function marketRecord(m, year, marketingSpend, newPlantingsAcres, supplyByRegime) {
  m.history.years.push(year);
  m.history.prices.push(m.currentPrice);
  m.history.supplies.push(m.currentSupply);
  m.history.demands.push(m.currentDemand);
  m.history.marketing.push(marketingSpend);
  m.history.newPlantings.push(newPlantingsAcres);
  m.history.supplyByRegime.push(supplyByRegime);
}

// ---- Events --------------------------------------------------------------

const EVENTS = {
  ahaEndorsement() {
    return {
      name: "AHA 'qualified' endorsement",
      description: "After heavy industry lobbying, the American Heart Association issues a 'qualified' health endorsement of almonds. Baseline demand rises 35%. (Reisman p.&nbsp;7.)",
      apply(market) { market.baselineDemand *= 1.35; },
    };
  },
  drought(severity = 0.8) {
    return {
      name: "Drought year",
      description: "Multi-year drought tightens water allocations. Intensive orchards lose yield; rainfed Spanish-style plantings shrug it off. (Reisman ch. 2.)",
      apply(_, orchards) {
        const loss = Math.max(0, Math.min(0.6, severity * 0.30));
        for (const o of orchards) o.currentYearIntensiveYieldModifier *= (1 - loss);
      },
    };
  },
  varroa() {
    return {
      name: "Varroa mite outbreak",
      description: "Varroa destructor sweeps managed hives. Beekeepers raise rental prices. Self-compatible varieties dodge the bill. (Reisman p.&nbsp;79, 92.)",
      apply(_, orchards, year) {
        for (const o of orchards) {
          if (o.usesSelfCompatibleVariety) continue;
          let needBees = 0;
          for (const c of o.cohorts) {
            if (c.regime !== REGIME.RAINFED && cohortIsProductive(c, year)) needBees += c.acres;
          }
          o.capital -= 100 * needBees;
        }
      },
    };
  },
  chinaExport() {
    return {
      name: "China export market opens",
      description: "The Almond Board's investment in Asian advertising pays off. Baseline demand rises 20%. (Reisman p.&nbsp;8-9.)",
      apply(market) { market.baselineDemand *= 1.20; },
    };
  },
  panicLevy() {
    return {
      name: "Panic levy increase",
      description: "The Almond Board, alarmed by nursery-sale projections, gets USDA approval to raise the per-pound assessment by 33%. (Reisman p.&nbsp;7.)",
      apply(market) { market.levyRate *= 1.33; },
    };
  },
  frost() {
    return {
      name: "Late spring frost",
      description: "Cold snap during bloom. Yields drop ~25% across the board.",
      apply(_, orchards) {
        for (const o of orchards) o.currentYearYieldModifier *= 0.75;
      },
    };
  },
};

// ---- Archetypes ----------------------------------------------------------

function signalFor(market, anticipationWeight) {
  const priceSignal = (market.currentPrice / market.referencePrice) - 1.0;
  const growth = marketProjectedSupplyGrowth5yr(market);
  return (1 - anticipationWeight) * priceSignal + anticipationWeight * (-growth);
}

function decideSpanishRainfed(year, market, o) {
  const d = { plantAcres: 0, plantRegime: REGIME.RAINFED, removeAcres: 0, marketingContribution: 0, switchToSelfCompatible: false };
  if (o.bankrupt) return d;
  const sig = signalFor(market, 0.10);
  if (sig > 0.20 && o.capital > 50_000) {
    d.plantAcres = Math.min(15, o.capital / 1000);
  }
  return d;
}

function decideCaliforniaIntensive(year, market, o) {
  const d = { plantAcres: 0, plantRegime: REGIME.INTENSIVE, removeAcres: 0, marketingContribution: 0, switchToSelfCompatible: false };
  if (o.bankrupt) return d;
  const sig = signalFor(market, 0.50);
  const reserve = orchardOperatingCost(o, year) * 2;
  const investable = Math.max(0, o.capital - reserve);
  if (sig > 0.10 && investable > 50_000) {
    const maxAffordable = investable / 9000;
    d.plantAcres = Math.min(150, maxAffordable);
  } else if (sig < -0.30 && orchardBearingAcres(o, year) > 100) {
    d.removeAcres = Math.min(50, orchardTotalAcres(o) * 0.10);
  }
  return d;
}

function decideInvestorMegaplanting(year, market, o) {
  const d = { plantAcres: 0, plantRegime: REGIME.SUPERINTENSIVE, removeAcres: 0, marketingContribution: 0, switchToSelfCompatible: false };
  if (o.bankrupt) return d;
  const growth = marketProjectedSupplyGrowth5yr(market);
  const reserve = orchardOperatingCost(o, year) * 3;
  const investable = Math.max(0, o.capital - reserve);
  if (market.currentPrice > market.referencePrice * 0.7 && growth < 0.50) {
    const maxAcres = investable / 14000;
    d.plantAcres = Math.min(200, maxAcres);
  }
  return d;
}

const ARCHETYPES = {
  rainfed: {
    name: 'Spanish rainfed smallholder',
    short: 'Smallholder',
    decide: decideSpanishRainfed,
    startingCapital: 80_000,
    startingAcres: 20,
    startingRegime: REGIME.RAINFED,
    anticipationWeight: 0.10,
    usesSelfCompatible: true,
    description: '"Almonds are what you grow where you can\'t grow anything else." Polyvalent, low-debt, slow to adopt.',
    cite: 'p. 8-9',
  },
  intensive: {
    name: 'California intensive grower',
    short: 'Intensive',
    decide: decideCaliforniaIntensive,
    startingCapital: 600_000,
    startingAcres: 150,
    startingRegime: REGIME.INTENSIVE,
    anticipationWeight: 0.50,
    usesSelfCompatible: false,
    description: 'Cochrane\'s classic subject. Drip irrigation, agrichemicals, trucked-in honeybees. Watches the forecast.',
    cite: 'p. 14',
  },
  investor: {
    name: 'Investor megaplanting',
    short: 'Investor',
    decide: decideInvestorMegaplanting,
    startingCapital: 12_000_000,
    startingAcres: 300,
    startingRegime: REGIME.SUPERINTENSIVE,
    anticipationWeight: 0.30,
    usesSelfCompatible: false,
    description: '"The darling of investment groups." Corporate capital, superintensive hedgerow, long horizon.',
    cite: 'p. 12',
  },
};

const DEFAULT_STARTING_TREE_AGE = 10;

function makeOrchardFromArchetype(archKey, customName, isPlayer = false) {
  const a = ARCHETYPES[archKey];
  const o = makeOrchard({
    name: customName || a.name,
    capital: a.startingCapital,
    anticipationWeight: a.anticipationWeight,
    usesSelfCompatible: a.usesSelfCompatible,
    isPlayer,
  });
  o.cohorts.push(makeCohort(-DEFAULT_STARTING_TREE_AGE, a.startingAcres, a.startingRegime));
  return o;
}

// ---- Engine --------------------------------------------------------------

function makeGame({ playerArchKey }) {
  const market = makeMarket();
  // NPC orchards
  const orchards = [
    makeOrchardFromArchetype('rainfed'),
    makeOrchardFromArchetype('intensive'),
    makeOrchardFromArchetype('investor'),
  ];
  const archKeys = ['rainfed', 'intensive', 'investor'];

  // Insert player as a fourth orchard with their chosen archetype
  const playerOrchard = makeOrchardFromArchetype(playerArchKey, 'You', true);
  orchards.push(playerOrchard);
  archKeys.push(playerArchKey);

  // Schedule of fixed events
  const schedule = {
    3: [EVENTS.ahaEndorsement()],
    8: [EVENTS.varroa()],
    10: [EVENTS.chinaExport()],
    14: [EVENTS.drought(0.8)],
    15: [EVENTS.drought(0.8)],
    16: [EVENTS.panicLevy()],
  };

  return {
    year: 0,
    market,
    orchards,
    archKeys,
    schedule,
    rng: mulberry32(42 + Math.floor(Math.random() * 1000)), // small seed entropy
    log: [],
    playerArchKey,
  };
}

function mulberry32(a) {
  return function() {
    let t = a += 0x6D2B79F5;
    t = Math.imul(t ^ t >>> 15, t | 1);
    t ^= t + Math.imul(t ^ t >>> 7, t | 61);
    return ((t ^ t >>> 14) >>> 0) / 4294967296;
  };
}

function updateMarketProjection(state) {
  const proj = [];
  for (let h = 0; h <= 10; h++) {
    const futureYear = state.year + h;
    let bearing = 0;
    for (const o of state.orchards) {
      if (o.bankrupt) continue;
      for (const c of o.cohorts) {
        if (cohortIsProductive(c, futureYear)) bearing += c.acres;
      }
    }
    proj.push(bearing);
  }
  marketUpdateProjection(state.market, proj);
}

function eventsForYear(state) {
  const out = [];
  if (state.schedule[state.year]) out.push(...state.schedule[state.year]);
  // Stochastic chance per year (lower than Python — this is a tighter game)
  if (state.rng() < 0.18) {
    const stochastic = [EVENTS.drought, EVENTS.varroa, EVENTS.frost];
    const idx = Math.floor(state.rng() * stochastic.length);
    out.push(stochastic[idx]());
  }
  return out;
}

// Run one year. `playerDecision` is what the human chose; if null, NPC logic runs.
function runTurn(state, playerDecision) {
  const report = {
    year: state.year,
    price: 0,
    totalSupplyMillionLb: 0,
    marketingSpend: 0,
    newPlantingsAcres: 0,
    bankruptcies: [],
    firedEvents: [],
    supplyByRegime: { rainfed: 0, intensive: 0, superintensive: 0 },
    playerProfit: 0,
    playerCapital: 0,
  };

  // 1. Events
  for (const ev of eventsForYear(state)) {
    ev.apply(state.market, state.orchards, state.year);
    report.firedEvents.push({ name: ev.name, description: ev.description });
  }

  // 2. Projection
  updateMarketProjection(state);

  // 3. Decisions
  const decisions = state.orchards.map((o, i) => {
    if (o.isPlayer && playerDecision) return playerDecision;
    const ak = state.archKeys[i];
    return ARCHETYPES[ak].decide(state.year, state.market, o);
  });

  // 4. Apply plantings/removals
  let newPlantingsTotal = 0;
  for (let i = 0; i < state.orchards.length; i++) {
    const o = state.orchards[i];
    const d = decisions[i];
    if (d.switchToSelfCompatible && !o.usesSelfCompatibleVariety) {
      // Conversion cost is charged by the UI for the player; for NPCs nobody flips
      o.usesSelfCompatibleVariety = true;
    }
    if (d.removeAcres > 0) orchardRemove(o, state.year, d.removeAcres);
    if (d.plantAcres > 0) {
      const ok = orchardPlant(o, state.year, d.plantAcres, d.plantRegime);
      if (ok) newPlantingsTotal += d.plantAcres;
    }
  }
  report.newPlantingsAcres = newPlantingsTotal;

  // 5. Total supply
  let totalSupplyLb = 0;
  for (const o of state.orchards) {
    if (o.bankrupt) continue;
    const lb = orchardProduce(o, state.year);
    totalSupplyLb += lb;
    // Distribute by dominant regime for chart
    for (const c of o.cohorts) {
      let cy = cohortYieldLb(c, state.year) * o.currentYearYieldModifier;
      if (c.regime !== REGIME.RAINFED) cy *= o.currentYearIntensiveYieldModifier;
      report.supplyByRegime[c.regime] += cy / 1_000_000;
    }
  }
  const totalSupplyMillion = totalSupplyLb / 1_000_000;
  report.totalSupplyMillionLb = totalSupplyMillion;

  // 6. Marketing: collect levy from intensive bearing yield + voluntary contributions
  let levyEligibleLb = 0;
  for (const o of state.orchards) {
    if (o.bankrupt) continue;
    for (const c of o.cohorts) {
      if (c.regime !== REGIME.RAINFED && cohortIsProductive(c, state.year)) {
        let y = cohortYieldLb(c, state.year) * o.currentYearYieldModifier * o.currentYearIntensiveYieldModifier;
        levyEligibleLb += y;
      }
    }
  }
  const levyRevenue = levyEligibleLb * state.market.levyRate;
  const voluntary = decisions.reduce((s, d) => s + (d.marketingContribution || 0), 0);
  const totalMarketing = levyRevenue + voluntary;
  marketSpendMarketing(state.market, totalMarketing);
  marketDecayMarketing(state.market);
  report.marketingSpend = totalMarketing;

  // 7. Clear market
  const price = marketClear(state.market, totalSupplyMillion);
  report.price = price;

  // 8. Settle each orchard
  const playerOrchard = state.orchards.find(o => o.isPlayer);
  const playerCapBefore = playerOrchard.capital;
  for (const o of state.orchards) {
    if (o.bankrupt) continue;
    orchardSettle(o, state.year, price, state.market.levyRate);
    if (o.bankrupt) report.bankruptcies.push(o.name);
  }
  report.playerProfit = playerOrchard.capital - playerCapBefore;
  report.playerCapital = playerOrchard.capital;

  // 9. Record + advance
  marketRecord(state.market, state.year, totalMarketing, newPlantingsTotal, { ...report.supplyByRegime });
  state.year += 1;
  state.log.push(report);
  return report;
}

// ---- UI ------------------------------------------------------------------

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

const fmtMoney = (n) => {
  const sign = n < 0 ? '-' : '';
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${sign}$${(abs/1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `${sign}$${(abs/1e6).toFixed(2)}M`;
  if (abs >= 1e3) return `${sign}$${(abs/1e3).toFixed(0)}K`;
  return `${sign}$${abs.toFixed(0)}`;
};
const fmtMoneyExact = (n) => {
  const sign = n < 0 ? '-' : '';
  const abs = Math.abs(n);
  return `${sign}$${Math.round(abs).toLocaleString('en-US')}`;
};
const fmtPct = (n) => `${n >= 0 ? '+' : ''}${(n * 100).toFixed(1)}%`;
const fmtNum = (n) => Math.round(n).toLocaleString('en-US');

let GAME = null;
let SELECTED_ARCH = null;
const TOTAL_YEARS = 25;
let ORIGINAL_DECISION_PANEL_HTML = null;

// --- Setup screen wiring ---

function renderArchetypePicker() {
  const root = $('#archetype-picker');
  root.innerHTML = '';
  for (const [key, a] of Object.entries(ARCHETYPES)) {
    const btn = document.createElement('button');
    btn.className = 'archetype';
    btn.dataset.key = key;
    btn.innerHTML = `
      <div class="archetype-meta">${a.short} · ${a.cite}</div>
      <div class="archetype-name">${a.name}</div>
      <div class="archetype-desc">${a.description}</div>
    `;
    btn.addEventListener('click', () => {
      SELECTED_ARCH = key;
      $$('.archetype').forEach(el => el.classList.toggle('selected', el === btn));
      $('#start-btn').disabled = false;
      $('.setup-hint').textContent = `Selected: ${a.name}`;
    });
    root.appendChild(btn);
  }
}

function startGame() {
  if (!SELECTED_ARCH) return;
  // Restore the decision panel in case a previous demo replaced it
  if (ORIGINAL_DECISION_PANEL_HTML) {
    $('.decision-panel').innerHTML = ORIGINAL_DECISION_PANEL_HTML;
    $('.decision-panel').classList.remove('demo-mode');
    $('#advance-btn').addEventListener('click', advanceYear);
    $('#plant-regime').addEventListener('change', () => { if (GAME) updatePlantHint(); });
    $('#plant-acres').addEventListener('input', () => { if (GAME) updatePlantHint(); });
  }
  GAME = makeGame({ playerArchKey: SELECTED_ARCH });
  // Prime the initial market clearing so year-zero charts have a value
  let supply = 0;
  for (const o of GAME.orchards) supply += orchardProduce(o, 0);
  marketClear(GAME.market, supply / 1_000_000);
  updateMarketProjection(GAME);
  // Record a "year -1" baseline so the chart shows the starting state
  marketRecord(GAME.market, -1, 0, 0, { rainfed: 0, intensive: 0, superintensive: 0 });

  $('#setup-screen').classList.add('hidden');
  $('#game-screen').classList.remove('hidden');
  refreshAll();
}

// --- Main game-screen rendering ---

function refreshAll() {
  refreshMasthead();
  drawCharts();
  renderField();
  renderDecision();
  renderLog();
}

function refreshMasthead() {
  const m = GAME.market;
  $('#meta-year').textContent = `${GAME.year} / ${TOTAL_YEARS}`;
  const priceEl = $('#meta-price');
  priceEl.textContent = `$${m.currentPrice.toFixed(2)}`;
  priceEl.className = 'meta-value';
  if (m.currentPrice < m.referencePrice * 0.85) priceEl.classList.add('warn');
  else if (m.currentPrice > m.referencePrice * 1.2) priceEl.classList.add('cool');
  const projEl = $('#meta-projection');
  const growth = marketProjectedSupplyGrowth5yr(m);
  projEl.textContent = fmtPct(growth);
  projEl.className = 'meta-value';
  if (growth > 0.20) projEl.classList.add('warn');
  else if (growth < -0.05) projEl.classList.add('cool');
}

// --- Charts ---

function drawCharts() {
  drawPriceChart();
  drawSupplyChart();
}

function drawPriceChart() {
  const svg = $('#price-chart');
  const W = 800, H = 220, padL = 40, padR = 16, padT = 14, padB = 24;
  const m = GAME.market;
  const years = m.history.years;
  const prices = m.history.prices;
  const xs = (yr) => {
    const yMin = -1, yMax = TOTAL_YEARS;
    return padL + (yr - yMin) / (yMax - yMin) * (W - padL - padR);
  };
  const yMax = 8;
  const ys = (p) => padT + (1 - Math.min(p, yMax) / yMax) * (H - padT - padB);

  let svgInner = '';
  // Gridlines
  for (let p = 1; p <= yMax; p++) {
    const yy = ys(p);
    svgInner += `<line class="gridline" x1="${padL}" y1="${yy}" x2="${W - padR}" y2="${yy}"/>`;
  }
  // Reference price (dashed)
  const refY = ys(m.referencePrice);
  svgInner += `<line class="price-ref-line" x1="${padL}" y1="${refY}" x2="${W - padR}" y2="${refY}"/>`;
  svgInner += `<text class="price-ref-label" x="${W - padR - 4}" y="${refY - 4}" text-anchor="end">reference $2.50</text>`;

  // Y-axis labels
  for (let p = 0; p <= yMax; p += 2) {
    svgInner += `<text class="axis-text" x="${padL - 6}" y="${ys(p) + 3}" text-anchor="end">$${p}</text>`;
  }
  // X-axis labels
  for (let yr = 0; yr <= TOTAL_YEARS; yr += 5) {
    svgInner += `<text class="axis-text" x="${xs(yr)}" y="${H - 6}" text-anchor="middle">${yr}</text>`;
  }
  // Axis lines
  svgInner += `<line class="axis-line" x1="${padL}" y1="${padT}" x2="${padL}" y2="${H - padB}"/>`;
  svgInner += `<line class="axis-line" x1="${padL}" y1="${H - padB}" x2="${W - padR}" y2="${H - padB}"/>`;

  // Price area + line
  if (years.length > 0) {
    let area = `M ${xs(years[0])} ${H - padB} `;
    let path = '';
    for (let i = 0; i < years.length; i++) {
      const cmd = i === 0 ? 'M' : 'L';
      path += `${cmd} ${xs(years[i]).toFixed(1)} ${ys(prices[i]).toFixed(1)} `;
      area += `L ${xs(years[i]).toFixed(1)} ${ys(prices[i]).toFixed(1)} `;
    }
    area += `L ${xs(years[years.length-1])} ${H - padB} Z`;
    svgInner += `<path class="price-fill" d="${area}"/>`;
    svgInner += `<path class="price-line" d="${path}"/>`;
    // marker on last point
    const last = years.length - 1;
    svgInner += `<circle class="price-marker" cx="${xs(years[last])}" cy="${ys(prices[last])}" r="3.5"/>`;
  }
  svg.innerHTML = svgInner;
}

function drawSupplyChart() {
  const svg = $('#supply-chart');
  const W = 800, H = 220, padL = 40, padR = 16, padT = 14, padB = 24;
  const m = GAME.market;
  const years = m.history.years;
  const supplies = m.history.supplyByRegime;

  // Find max y - include both realized and projected
  let maxY = 4;
  for (const r of supplies) maxY = Math.max(maxY, r.rainfed + r.intensive + r.superintensive);
  // Estimate projected supply for the visualization: use the projected bearing
  // acres curve scaled by an industry-wide weighted yield estimate.
  const projAcres = m.projectedBearingAcres;
  // Estimate avg yield per bearing acre from current supply mix
  const totalBearingNow = projAcres[0] || 1;
  const totalSupplyNow = m.currentSupply;
  const avgYieldPerAcre = totalSupplyNow / totalBearingNow * 1; // million lb / acre
  const projectedSupply = projAcres.map(a => a * avgYieldPerAcre);
  for (const v of projectedSupply) maxY = Math.max(maxY, v);
  maxY = Math.ceil(maxY * 1.1);

  const xs = (yr) => {
    const yMin = -1, yMax = TOTAL_YEARS;
    return padL + (yr - yMin) / (yMax - yMin) * (W - padL - padR);
  };
  const ys = (s) => padT + (1 - s / maxY) * (H - padT - padB);
  const barWidth = (W - padL - padR) / (TOTAL_YEARS + 1) * 0.75;

  let svgInner = '';

  // Gridlines
  const yStep = Math.max(1, Math.floor(maxY / 4));
  for (let s = yStep; s <= maxY; s += yStep) {
    const yy = ys(s);
    svgInner += `<line class="gridline" x1="${padL}" y1="${yy}" x2="${W - padR}" y2="${yy}"/>`;
    svgInner += `<text class="axis-text" x="${padL - 6}" y="${yy + 3}" text-anchor="end">${s}</text>`;
  }
  for (let yr = 0; yr <= TOTAL_YEARS; yr += 5) {
    svgInner += `<text class="axis-text" x="${xs(yr)}" y="${H - 6}" text-anchor="middle">${yr}</text>`;
  }

  // Projected supply ghost (years from current+1 to current+5)
  if (GAME.year > 0 || GAME.year >= 0) {
    let ghostPath = '';
    for (let h = 0; h <= 5; h++) {
      const yr = GAME.year + h;
      if (yr > TOTAL_YEARS) break;
      const supply = projectedSupply[h];
      const cmd = h === 0 ? 'M' : 'L';
      ghostPath += `${cmd} ${xs(yr).toFixed(1)} ${ys(supply).toFixed(1)} `;
    }
    if (ghostPath) {
      svgInner += `<path class="supply-projected" d="${ghostPath}" fill="none"/>`;
      // Add a faded fill below the ghost line
      let ghostArea = `M ${xs(GAME.year)} ${H - padB} `;
      for (let h = 0; h <= 5; h++) {
        const yr = GAME.year + h;
        if (yr > TOTAL_YEARS) break;
        ghostArea += `L ${xs(yr).toFixed(1)} ${ys(projectedSupply[h]).toFixed(1)} `;
      }
      const lastH = Math.min(5, TOTAL_YEARS - GAME.year);
      ghostArea += `L ${xs(GAME.year + lastH)} ${H - padB} Z`;
      svgInner += `<path class="supply-projected" d="${ghostArea}"/>`;
    }
  }

  // Realized supply: stacked bars (rainfed + intensive + superintensive)
  for (let i = 0; i < years.length; i++) {
    const yr = years[i];
    const r = supplies[i];
    const x = xs(yr) - barWidth / 2;
    let stackTop = 0;
    for (const regime of ['rainfed', 'intensive', 'superintensive']) {
      const v = r[regime];
      if (v <= 0) continue;
      const barTop = ys(stackTop + v);
      const barBottom = ys(stackTop);
      svgInner += `<rect class="supply-bar ${regime}" x="${x}" y="${barTop}" width="${barWidth}" height="${barBottom - barTop}"/>`;
      stackTop += v;
    }
  }

  // Axis lines
  svgInner += `<line class="axis-line" x1="${padL}" y1="${padT}" x2="${padL}" y2="${H - padB}"/>`;
  svgInner += `<line class="axis-line" x1="${padL}" y1="${H - padB}" x2="${W - padR}" y2="${H - padB}"/>`;

  svg.innerHTML = svgInner;
}

// --- Field (orchards) ---

function renderField() {
  const root = $('#field');
  root.innerHTML = '';
  for (const o of GAME.orchards) {
    const card = document.createElement('div');
    card.className = 'orchard' + (o.isPlayer ? ' player' : '') + (o.bankrupt ? ' bankrupt' : '');

    const totalAcres = orchardTotalAcres(o);
    const bearing = orchardBearingAcres(o, GAME.year);
    const by = orchardAcresByRegime(o);
    const dominant = orchardDominantRegime(o);

    let html = `
      <h3 class="orchard-name">
        ${o.name}
        ${o.isPlayer ? '<span class="you-marker">You</span>' : ''}
      </h3>
      <div class="orchard-stats">
        <div class="stat"><span>Capital</span><span class="v">${fmtMoney(o.capital)}</span></div>
        <div class="stat"><span>Cum. profit</span><span class="v">${fmtMoney(o.cumulativeProfit)}</span></div>
        <div class="stat"><span>Total acres</span><span class="v">${fmtNum(totalAcres)}</span></div>
        <div class="stat"><span>Bearing</span><span class="v">${fmtNum(bearing)}</span></div>
      </div>
      <div class="bars">
    `;
    // Regime bars (relative to that orchard's max acres)
    const denom = Math.max(totalAcres, 1);
    for (const regime of ['rainfed', 'intensive', 'superintensive']) {
      const acres = by[regime];
      if (acres <= 0 && dominant !== regime) continue;
      const pct = (acres / denom) * 100;
      html += `
        <div class="bar-row">
          <div>${REGIME_LABEL[regime]}</div>
          <div class="bar-track"><div class="bar-fill ${regime}" style="width:${pct}%"></div></div>
          <div class="bar-value">${fmtNum(acres)}</div>
        </div>
      `;
    }
    if (o.saltBurden > 0.05 && (by.intensive + by.superintensive) > 0) {
      html += `
        <div class="bar-row">
          <div>Salt</div>
          <div class="bar-track"><div class="bar-fill salt" style="width:${(o.saltBurden*100).toFixed(0)}%"></div></div>
          <div class="bar-value">${(o.saltBurden*100).toFixed(0)}%</div>
        </div>
      `;
    }
    html += `</div>`;
    if (o.bankrupt) html += `<div class="bankrupt-stamp">Bankrupt</div>`;
    card.innerHTML = html;
    root.appendChild(card);
  }
}

// --- Decision panel ---

function renderDecision() {
  // If we're in demo mode, the decision panel has been replaced with a banner.
  if (!$('#plant-acres')) return;
  const player = GAME.orchards.find(o => o.isPlayer);
  $('#decision-year').textContent = GAME.year;
  // Update variety block based on state
  const varietyBlock = $('#variety-block');
  const switchEl = $('#switch-variety');
  const varietyLabel = varietyBlock.querySelector('.lbl');
  const varietyHint = varietyBlock.querySelector('.hint');
  if (player.usesSelfCompatibleVariety) {
    varietyBlock.style.opacity = '0.65';
    switchEl.disabled = true;
    switchEl.checked = true;
    varietyLabel.innerHTML = `<input type="checkbox" id="switch-variety" checked disabled> Self-compatible varieties (already in use)`;
    varietyHint.innerHTML = `Spanish Guara line, est. 1986. No honeybee rental cost. <span class="cite">(Reisman p.&nbsp;92)</span>`;
  } else {
    varietyBlock.style.opacity = '';
    switchEl.disabled = false;
    switchEl.checked = false;
    varietyLabel.innerHTML = `<input type="checkbox" id="switch-variety"> Switch to self-compatible varieties`;
    varietyHint.innerHTML = `Spanish Guara line, est. 1986. Costs $50,000 to convert, but eliminates honeybee rental. <span class="cite">(Reisman p.&nbsp;92)</span>`;
  }
  // Reset values
  $('#plant-acres').value = 0;
  $('#remove-acres').value = 0;
  $('#marketing-voluntary').value = 0;

  // Update plant hint with current capital affordability
  updatePlantHint();

  // Disable advance if game over
  $('#advance-btn').disabled = (GAME.year >= TOTAL_YEARS) || player.bankrupt;
  if (player.bankrupt) {
    $('#advance-status').textContent = 'You are bankrupt — push “Advance year” to finish out the simulation.';
    $('#advance-status').className = 'status alert';
    $('#advance-btn').disabled = false;
  } else {
    $('#advance-status').textContent = '';
    $('#advance-status').className = 'status';
  }
}

function updatePlantHint() {
  if (!$('#plant-hint')) return;
  const player = GAME.orchards.find(o => o.isPlayer);
  const regime = $('#plant-regime').value;
  const cost = ESTABLISHMENT_COST[regime];
  const affordable = Math.floor(player.capital / cost);
  $('#plant-hint').innerHTML =
    `Establishment cost: <code>${fmtMoneyExact(cost)}</code>/acre · Affordable now: <b>${fmtNum(affordable)}</b> acres. ` +
    `Trees take 4 years to bear and 20 to remove. <span class="cite">(Reisman p.&nbsp;14)</span>`;
}

// --- Log ---

function renderLog() {
  const root = $('#log');
  root.innerHTML = '';
  // Most recent first
  for (let i = GAME.log.length - 1; i >= 0; i--) {
    const r = GAME.log[i];
    const li = document.createElement('li');
    li.className = 'log-entry';
    let html = `
      <span class="log-year">Year ${r.year}</span>
      <div class="log-text">
        <span class="nums">
          <span>Price <b>$${r.price.toFixed(2)}</b></span>
          <span>Supply <b>${r.totalSupplyMillionLb.toFixed(2)}M lb</b></span>
          <span>Industry plantings <b>${fmtNum(r.newPlantingsAcres)} acres</b></span>
          <span>Marketing <b>${fmtMoney(r.marketingSpend)}</b></span>
          <span>Your profit <b>${fmtMoney(r.playerProfit)}</b></span>
        </span>
    `;
    for (const ev of r.firedEvents) {
      html += `<span class="event">${ev.name} — ${ev.description}</span>`;
    }
    for (const b of r.bankruptcies) {
      html += `<span class="bankruptcy">Bankruptcy: ${b}</span>`;
    }
    html += `</div>`;
    li.innerHTML = html;
    root.appendChild(li);
  }
}

// --- Decision capture & advance ---

function captureDecision() {
  const player = GAME.orchards.find(o => o.isPlayer);
  const plantAcres = Math.max(0, parseInt($('#plant-acres').value) || 0);
  const plantRegime = $('#plant-regime').value;
  const removeAcres = Math.max(0, parseInt($('#remove-acres').value) || 0);
  const voluntary = Math.max(0, parseInt($('#marketing-voluntary').value) || 0);
  const wantsSwitch = $('#switch-variety').checked && !player.usesSelfCompatibleVariety;

  // Validate: planting cost
  const cost = ESTABLISHMENT_COST[plantRegime] * plantAcres;
  if (cost > player.capital) {
    alert(`You can't afford ${fmtNum(plantAcres)} acres of ${plantRegime}: it would cost ${fmtMoneyExact(cost)} but you have ${fmtMoneyExact(player.capital)}.`);
    return null;
  }
  if (voluntary > player.capital) {
    alert(`You can't contribute ${fmtMoneyExact(voluntary)} to marketing — you have ${fmtMoneyExact(player.capital)}.`);
    return null;
  }
  if (wantsSwitch && player.capital < 50_000 + cost + voluntary) {
    alert(`You can't afford the $50,000 variety conversion plus your other choices.`);
    return null;
  }
  // Apply variety conversion fee here
  if (wantsSwitch) player.capital -= 50_000;

  return {
    plantAcres,
    plantRegime,
    removeAcres,
    marketingContribution: voluntary,
    switchToSelfCompatible: wantsSwitch,
  };
}

function advanceYear() {
  const player = GAME.orchards.find(o => o.isPlayer);
  let decision = null;
  if (!player.bankrupt) {
    decision = captureDecision();
    if (decision === null) return;
  }
  runTurn(GAME, decision);
  if (GAME.year >= TOTAL_YEARS) {
    refreshAll();
    showEndScreen();
    return;
  }
  refreshAll();
}

function showEndScreen() {
  const player = GAME.orchards.find(o => o.isPlayer);
  $('#game-screen').classList.add('hidden');
  $('#end-screen').classList.remove('hidden');
  const summary = $('#end-summary');
  const totalAcres = orchardTotalAcres(player);
  const cls = player.cumulativeProfit < 0 ? 'warn' : (player.cumulativeProfit > 1_000_000 ? 'cool' : '');
  summary.innerHTML = `
    <div class="end-stat"><span class="label">Final capital</span><span class="value ${cls}">${fmtMoneyExact(player.capital)}</span></div>
    <div class="end-stat"><span class="label">Cumulative profit</span><span class="value ${cls}">${fmtMoneyExact(player.cumulativeProfit)}</span></div>
    <div class="end-stat"><span class="label">Final total acres</span><span class="value">${fmtNum(totalAcres)}</span></div>
    <div class="end-stat"><span class="label">Bankrupt</span><span class="value ${player.bankrupt ? 'warn' : 'cool'}">${player.bankrupt ? 'Yes' : 'No'}</span></div>
    <div class="end-stat"><span class="label">Salt burden</span><span class="value">${(player.saltBurden*100).toFixed(0)}%</span></div>
    <div class="end-stat"><span class="label">Self-compatible variety</span><span class="value">${player.usesSelfCompatibleVariety ? 'Yes' : 'No'}</span></div>
  `;
}

function restart() {
  if (DEMO_TIMER) { clearInterval(DEMO_TIMER); DEMO_TIMER = null; }
  GAME = null;
  SELECTED_ARCH = null;
  // Restore decision panel HTML so the next "Begin year zero" finds its inputs
  if (ORIGINAL_DECISION_PANEL_HTML) {
    $('.decision-panel').innerHTML = ORIGINAL_DECISION_PANEL_HTML;
    $('.decision-panel').classList.remove('demo-mode');
  }
  $('#end-screen').classList.add('hidden');
  $('#game-screen').classList.add('hidden');
  $('#setup-screen').classList.remove('hidden');
  $$('.archetype').forEach(el => el.classList.remove('selected'));
  $('#start-btn').disabled = true;
  $('.setup-hint').textContent = 'Pick an archetype above to begin.';
}

// --- Wire it all up ---

document.addEventListener('DOMContentLoaded', () => {
  ORIGINAL_DECISION_PANEL_HTML = $('.decision-panel').innerHTML;
  renderArchetypePicker();
  $('#start-btn').addEventListener('click', startGame);
  $('#demo-btn').addEventListener('click', startDemo);
  $('#advance-btn').addEventListener('click', advanceYear);
  $('#restart-btn').addEventListener('click', restart);
  $('#plant-regime').addEventListener('change', () => {
    if (GAME) updatePlantHint();
  });
  $('#plant-acres').addEventListener('input', () => {
    if (GAME) updatePlantHint();
  });
});

// --- Demo / auto-play -----------------------------------------------------

let DEMO_TIMER = null;

function startDemo() {
  // Default to intensive if user hasn't picked
  if (!SELECTED_ARCH) SELECTED_ARCH = 'intensive';
  GAME = makeGame({ playerArchKey: SELECTED_ARCH });
  let supply = 0;
  for (const o of GAME.orchards) supply += orchardProduce(o, 0);
  marketClear(GAME.market, supply / 1_000_000);
  updateMarketProjection(GAME);
  marketRecord(GAME.market, -1, 0, 0, { rainfed: 0, intensive: 0, superintensive: 0 });

  $('#setup-screen').classList.add('hidden');
  $('#game-screen').classList.remove('hidden');

  // Hide the decision panel during demo, show a banner instead
  const decisionPanel = $('.decision-panel');
  decisionPanel.classList.add('demo-mode');
  decisionPanel.innerHTML = `
    <h2 class="panel-title">Auto-play<span class="panel-tag">Watching the cycle</span></h2>
    <p class="demo-text">
      All four orchards make the same decisions an NPC would, including the
      one labeled <em>You</em>. Watch the price chart fill in. Notice how
      planting decisions in the early years arrive at the market years later,
      after the price has already moved on.
    </p>
    <p class="demo-text secondary">
      The faded sky-colored shape on the supply chart is the Almond Board's
      forward look — the supply that nursery sales have already committed to.
      <span class="cite">(Reisman p.&nbsp;14)</span>
    </p>
    <button class="btn btn-secondary" id="demo-stop">Stop and start a real game</button>
  `;
  $('#demo-stop').addEventListener('click', () => {
    if (DEMO_TIMER) { clearInterval(DEMO_TIMER); DEMO_TIMER = null; }
    restart();
  });

  refreshAll();

  DEMO_TIMER = setInterval(() => {
    if (GAME.year >= TOTAL_YEARS) {
      clearInterval(DEMO_TIMER);
      DEMO_TIMER = null;
      // Restore decision panel HTML for any restart, then show end screen
      showEndScreen();
      return;
    }
    runTurn(GAME, null);
    refreshAll();
  }, 600);
}
