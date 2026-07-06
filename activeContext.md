# Active Context

## Resume Here
- **Tier:** Script
- **Current Slice:** All slices complete (1–6, 8). Task 18 deferred.
- **Current Task:** N/A
- **Next Action:**
  1. `.venv\Scripts\pip install yfinance` — one-time install, not yet done
  2. Open Fava → Price Updater button → rewrites `prices\TICKER.bean` and `prices\TICKER_events.bean` via Yahoo
  3. Spot-check: `type prices\MGLU3_events.bean` — expect `custom "desdobramento"` with `^yahoo` tag
  4. `.venv\Scripts\python import.py extract export\ > tmp.bean`
  5. `.venv\Scripts\python reconcile_actions.py tmp.bean`
  6. Manually fill any `; ⚠ no Yahoo match` entries in `corporate_actions.bean`
  7. Bean-check: `python -c "import beancount.loader; entries,errors,opts=beancount.loader.load_file('main.bean'); [print(e) for e in errors]; print(len(errors),'errors')"`

## Completed This Session
- Slice 8: Yahoo Finance price service fully implemented
- `plugins/yahoo_price_service.py` — new; prices + splits + dividends via yfinance; `.SA` suffix; split ratio → desdobramento/grupamento/bonificacao; dividends → `dividendo` (reference only); `^yahoo` tag
- `plugins/price_updater.py` — swapped to YahooPriceUpdater; BRAPI service untouched
- `reconcile_actions.py` — tag-agnostic event loader; split-only enrichment; `sanity_check_income` removed; enrichment tag now `^b3-yahoo-enriched`
- `requirements.txt` — `yfinance>=0.2.0` added

## Blockers / Open Questions
- **yfinance not installed yet** — must `pip install yfinance` before Fava price update will work
- **Full pipeline not run on real data** — still needs fresh B3 export + reconcile run
- **Income reconciliation deferred** — Yahoo cannot distinguish JCP from dividendo; `dividendo` entries in `_events.bean` are reference only for now
- **11 "Not enough lots" on Asset Transfers** — broker migration rows (2023-05-31, 2025-02-14); manual lot matching needed
- **FII secondary offerings** (HGLG11, HGRU11, MCCI11, IRDM11, XPLG11, XPML11) — 9 errors; manual research needed
- **4 CategorizationError** (CVCB11, XPBR31) — fix manually in `transactions.bean`
- **Task 18** (`^b3` tag on importer entries) — deferred; `_meta()` has no `tags=` param

## Read These First
- `plan/tasks.md`: Slice 8 Tasks 19–22 `[x]`; Task 18 `[ ]` (deferred)
- `plan/decisions.md`: Decision [006] — Yahoo primary, BRAPI retained as dormant upgrade path
- `plugins/yahoo_price_service.py`: new primary service — read before touching price logic
- `plugins/brapi_price_service.py`: dormant reference — do not delete, do not wire up
- `reconcile_actions.py`: enrichment now uses `^b3-yahoo-enriched` tag; no income sanity-check
