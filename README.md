# trees-on-a-treadmill

A scenario-based game and simulation of the agricultural technological treadmill,
based on Emily Reisman's *The Almond Paradox: Cracking Open the Politics of What
Plants Need* (UC Press, 2025).

You run an almond orchard. The market won't sit still. Every year you choose
what to plant, what to spray, what to irrigate, whether to chip in for ads, and
whether to truck in honeybees. So does everyone else. Reisman's mechanisms are
the rules of the game: Cochrane's overproduction loop, the anticipatory pressure
unique to permanent crops, marketing as a collective technology that works until
it doesn't, and the way each input creates new lock-ins that get rendered as
the plant's biological "needs."

## Two ways to play

### 1. Web (no install — works on GitHub Pages)

Visit the deployed site, pick an archetype, advance one year at a time. The
browser version is a single-file simulation written in vanilla JS with no
build step. To run it locally:

```
cd web
python3 -m http.server 8000
# open http://localhost:8000/
```

There is also an "Auto-play" mode on the setup screen for classroom use,
which runs the simulation without player input so you can watch the
boom-and-crash cycle unfold.

### 2. Python CLI / scenario scripts

For automated runs, classroom demos, or analysis:

```
python -m game.cli                       # interactive text play
python -m scenarios.california_2000s     # auto-play the post-2000 boom-crash
python -m scenarios.spanish_rainfed      # the marginal-resilience case
python -m scenarios.investor_entry       # what happens when an investor enters
pytest                                   # 11 mechanism tests
node web/test_sim.js                     # 13 JS-side mirror tests
```

## What's modeled

The simulation implements four mechanisms from the book:

1. **Cochrane's classic loop** (Introduction, "Trees on a Treadmill", p. 14).
   Adoption raises early-adopter yields. Diffusion raises industry supply.
   Supply outpaces demand. Prices fall. Laggards must adopt, scale, or exit.
2. **Anticipatory adoption in permanent crops** (p. 14-15). Trees take ~4 years
   to bear and ~20 years to remove. The Almond Board tracks nursery sales and
   projects supply 3-10 years out. Players see those projections — the same
   forecast the Almond Board uses to decide when to panic. The treadmill runs
   on what people *expect*, not just what has happened.
3. **Marketing as collective technology** (p. 15-16). A USDA-style levy funds
   advertising that lifts demand. Lifted demand attracts new entrants. New
   entrants overshoot supply. The marketing strategy backfires.
4. **Input lock-in producing "needs"** (Chapters 1-3). Intensive irrigation
   triggers salt accumulation, requiring a leaching fraction. Pesticide-driven
   pollinator loss creates dependence on trucked-in honeybees. Thin-shell
   varieties deepen insecticide dependence. Each "need" is a political-economic
   product, not a biological given.

See [`data/citations.md`](data/citations.md) for the page-by-page mapping
between game mechanics and the book.

## Repo layout

```
game/
    market.py          Price formation, demand, marketing-driven demand shifts
    orchard.py         Player and NPC orchards: acres, age, intensification
    events.py          Drought, frost, AHA endorsement, varroa, panic levy
    archetypes.py      Spanish rainfed, California intensive, investor megaplanting
    engine.py          Per-turn simulation loop
    cli.py             Interactive text interface
scenarios/
    california_2000s.py    Replays the post-2000 California boom-crash
    spanish_rainfed.py     Marginal smallholder under EU subsidy pressure
    investor_entry.py      A new megaplanting joins an already-saturated market
data/
    citations.md           Page references mapped to game mechanics
tests/
    test_market.py         Market-clearing unit tests (5 tests)
    test_loop.py           Treadmill-emergence behavior tests (6 tests)
web/
    index.html             The web game
    style.css              Editorial paper-and-ink design system
    game.js                Vanilla JS simulation port (no build step)
    test_sim.js            JS-side mirror of the Python tests
    test_browser.py        Playwright end-to-end test
    test_demo.py           Auto-play (demo mode) end-to-end test
    test_mobile.py         Mobile viewport rendering test
    smoke.js               Quick CLI smoke test of the JS sim
```

The Python and JS implementations share identical constants and decision
rules, so the browser game produces the same dynamics the Python tests verify.

## Deploying to GitHub Pages

The `web/` directory is a complete static site. To serve it via GitHub Pages:

1. Push this repo to GitHub.
2. Go to **Settings → Pages**.
3. Under **Source**, choose "Deploy from a branch".
4. Choose your default branch and set the folder to `/web`.
5. Save. Within a minute or two the site will be live at
   `https://<username>.github.io/<repo>/`.

If you'd rather serve from the repo root, copy `web/index.html`,
`web/style.css`, and `web/game.js` to the root.

## A note on what this is and isn't

This is a teaching tool, not a forecast. The numbers are calibrated to
*feel* like Reisman's narrative — early adopters do well, the market does
crash, marketing does backfire, lock-ins do compound — but they are not fits
to USDA data. The point is to let players experience why "what plants need"
is a political claim.

## License

The code is offered for educational use. Reisman's book is © UC Press, 2025;
all argumentative substance is hers, and any errors of translation into game
mechanics are mine.
