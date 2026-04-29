// Quick smoke test of the JS simulation logic, bypassing the DOM.
// Run with: node web/smoke.js

const fs = require('fs');
const path = require('path');

// Load game.js as text and execute the non-DOM portions
const src = fs.readFileSync(path.join(__dirname, 'game.js'), 'utf-8');

// Strip the DOMContentLoaded handler and the UI-touching parts by evaluating only
// up to the "// ---- UI ----" marker.
const headerEnd = src.indexOf('// ---- UI');
const simSrc = src.slice(0, headerEnd);
// Need to remove `'use strict'` so eval works in non-strict mode
const cleaned = simSrc.replace(/^\s*'use strict'\s*;?/m, '');
eval(cleaned);

// Now test: build a game with the JS makeGame logic
const game = makeGame({ playerArchKey: 'intensive' });
let supply = 0;
for (const o of game.orchards) supply += orchardProduce(o, 0);
marketClear(game.market, supply / 1_000_000);

console.log('Year 0 starting price:', game.market.currentPrice.toFixed(2));
console.log('Year 0 starting supply (M lb):', (supply / 1e6).toFixed(2));

// Run 25 years with NPC logic for everyone (no player decision)
const reports = [];
for (let i = 0; i < 25; i++) {
  reports.push(runTurn(game, null));
}
console.log('\nYear-by-year:');
for (const r of reports) {
  console.log(
    `yr=${String(r.year).padStart(2)} price=$${r.price.toFixed(2)} ` +
    `supply=${r.totalSupplyMillionLb.toFixed(2)}M ` +
    `new_acres=${r.newPlantingsAcres.toFixed(0)} ` +
    `events=${r.firedEvents.map(e => e.name).join(' | ') || '—'}`
  );
}

console.log('\nFinal state:');
for (const o of game.orchards) {
  console.log(
    `  ${o.name}: cap=${o.capital.toFixed(0)} acres=${orchardTotalAcres(o).toFixed(0)} bankrupt=${o.bankrupt}`
  );
}
