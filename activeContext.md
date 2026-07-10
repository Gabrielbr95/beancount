# Active Context

## Resume Here
- **Tier:** Script
- **Current Slice:** Slice 10 — "Not enough lots" fix (DEFERRED by user)
- **Current Task:** Task 28 `[!]` — decide between Option B (bake splits into source) vs Option C (standalone pre-processor script)
- **Next Action:**
  1. Read `plan/decisions.md` decision [011] — full research notes on why pre-booking plugin is not viable (beancount hardcodes booking-before-plugins; Fava can't be hooked pre-booking).
  2. Decide Option B vs C. Option C (`scripts/apply_splits.py`) is the leading candidate — matches the `reconcile_actions.py` pipeline pattern and Script-tier philosophy.
  3. If Option C: scope it. Read `plugins/stock_split.py` for the transformation logic already written (it works correctly on entries; the problem is only that it runs too late in the pipeline). The script would reuse that logic but run as a pipeline step BEFORE `bean-check`, rewriting `transactions.bean` in place.
  4. Separately, clear the two trivial B3SA3 follow-ups (tasks 26, 27): fill ratio=3 in `corporate_actions.bean:23` and trigger a price updater run with `all_history: True` so `B3SA3.bean` + include get regenerated.

## Completed This Session
- **Diagnostics:** ran `bean-check main.bean` → 39 errors, categorized into 5 root causes (20 "Not enough lots", 13 "Too many missing numbers", 4 "Failed to categorize", 1 "Ratio 0 sentinel", 1 "Missing MALL11.bean include"). Full breakdown in chat history.
- **Fava query tip:** confirmed BQL `JOURNAL WHERE currency = 'PETR4'` filters to ticker transactions only, automatically excluding dividends/JCP (those are BRL-only postings, no ticker units).
- **B3SA3 root-cause fix (Task 23):** `BR_TICKER_RE` regex was `^[A-Z]{4}\d{1,2}$` — rejected B3SA3 because "B3" has a digit at position 2. Fixed to `^[A-Z0-9]{4,5}\d{1,2}$`. B3SA3 was the ONLY affected ticker of 28 tested. This is why B3SA3.bean / B3SA3_events.bean never existed — not a yfinance or sold-out issue.
- **all_history config flag (Task 24):** added to `YahooPriceUpdater`, default False. When True, includes fully-sold tickers (any ticker that ever appeared in `Assets:Investment:*`). Toggle: `2010-01-01 custom "fava-extension" "plugins.price_updater" "{'all_history': True}"`.
- **B3SA3 events file (Task 25):** generated `prices/B3SA3_events.bean` live from Yahoo. Split `desdobramento B3SA3 3` on 2021-05-17 present, matches `corporate_actions.bean` entry (2021-05-18) within ±5 day reconcile window. NOTE: Yahoo lists the split TWICE (2021-05-06 AND 2021-05-17, both ratio 3) — likely ex-date/record-date duplication; reconcile picks 2021-05-17 (drift 1). May want to delete the 2021-05-06 duplicate later.
- **Option 2 research (NOT viable):** confirmed via beancount 3.2.3 source + web that pre-booking plugins are impossible. Loader hardcodes parse → booking → plugins → validate. `PLUGINS_PRE`/`POST` is ordering among plugins, not relative to booking. `plugin_processing_mode` doesn't help. Martin Blais acknowledged this in 2020 as an unimplemented proposal. Bypassing the loader breaks Fava. `booking_method "NONE"` tested — produces different errors ("Too many missing numbers"), not a fix. Full notes in `plan/decisions.md` [011].

## Blockers / Open Questions
- **20 "Not enough lots" errors unresolved** — root cause is the booking-before-plugins ordering (decision [011]). Awaiting user decision on Option B vs C. This is the big one.
- **B3SA3 ratio still 0 in `corporate_actions.bean:23`** — events file now exists but the existing entry won't auto-enrich. Task 26.
- **13 "Too many missing numbers" + 4 "Failed to categorize"** — XPBR31 Sell and CVCB11/XPBR31 transfer entries with importer bugs (multiple BRL postings without amounts, empty-lot self-transfers). Not investigated this session; lower priority than the 20.
- **MALL11.bean missing** — `prices/prices.bean:20` includes a non-existent file (MALL11 was delisted/renamed). Trivial: remove the line.
- **Yahoo split duplication** — B3SA3 split listed on both 2021-05-06 and 2021-05-17. Cosmetic; reconcile handles it but cleanup possible.

## Read These First
- `plan/decisions.md` [011]: Full research on why pre-booking plugins are not viable in beancount 3.x. Read before revisiting the 20-error fix.
- `plan/decisions.md` [009], [010]: The B3SA3 regex fix and all_history flag — already implemented, logged for durability.
- `plan/tasks.md` Slice 9, 10: Tasks 23-25 done; 26-27 trivial follow-ups; 28-30 the deferred design decision.
- `plugins/yahoo_price_service.py`:30, 147-179: The two fixes (regex + all_history flag). Read before touching the updater.
- `plugins/stock_split.py`: The transformation logic that works correctly on entries but runs too late. Reusable if Option C (standalone script) is chosen.
- `transactions.bean`:868: The ITSA3 example case discussed in detail — 300 bought, bonificação to 315, sells of 1+14+300 fail because booking saw only 299 before the plugin transformed to 315.
