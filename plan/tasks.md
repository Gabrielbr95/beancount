# Implementation Plan

## Slice 1: Update B3 importer — differentiate corporate action types
- [x] 1. In `importers/b3.py`, replace the single `BONIFICACAO EM ATIVOS / DESDOBRO / GRUPAMENTO` block with three branches, each emitting its own directive name (`"bonificacao"`, `"desdobramento"`, `"grupamento"`), ratio `"0"` sentinel, tag `^b3`, and `quantity` in metadata. (Verification: run `python import.py extract export\ > tmp.bean`, grep tmp.bean for `custom "desdobramento"` — should appear with ratio 0 and ^b3 tag)

## Slice 2: Update BRAPI price service — api-agnostic directive names
- [x] 2. In `plugins/brapi_price_service.py`, update `_extract_events()` to map BRAPI `label` → directive name (`DESDOBRAMENTO→desdobramento`, etc.) and use ticker (not ISIN) as first value. (Verification: trigger a BRAPI update for MGLU3, inspect `prices/MGLU3_events.bean` — directives should read `custom "desdobramento" "MGLU3" ...` with `^brapi` tag)
- [x] 3. Update `_write_events_file()` to emit tags and keep all metadata fields (approvedOn, lastDatePrior, paymentDate, isinCode, label). (Verification: MGLU3_events.bean has all metadata fields present, no `brapi-` prefix in directive names)
- [x] 4. Remove `prices/*_events.bean` includes from `prices/prices.bean` index writer (`_write_index()`). (Verification: `prices/prices.bean` contains only `TICKER.bean` includes, no `_events` lines)

## Slice 3: Update stock_split.py — read new directive names
- [x] 5. In `plugins/stock_split.py`, replace `entry.type == "split"` with a check for `entry.type in {"desdobramento", "grupamento", "bonificacao"}`. (Verification: unit test — create a mock ledger with a `custom "desdobramento" "WEGE3" "2"` entry and a prior WEGE3 transaction; confirm units doubled)
- [x] 6. Add guard: if ratio == 0, append a `SplitError` with a clear message and skip the entry. (Verification: mock ledger with ratio "0" — error appears in output, no units modified)

## Slice 4: Write reconcile_actions.py
- [x] 7. Scaffold CLI: `argparse` with positional `tmp_bean` path and `--rewrite` flag. Fail loudly if `tmp.bean` does not exist. (Verification: `python reconcile_actions.py --help` shows usage; `python reconcile_actions.py missing.bean` prints clear error)
- [x] 8. Write `parse_tmp_bean()`: read tmp.bean as plain text, split entries by blank-line boundaries, classify each by type into three buckets (transactions, income, corporate_actions). (Verification: parse a known tmp.bean, print bucket counts — matches expected)
- [x] 9. Write `load_events_bean(prices_dir)`: parse all `*_events.bean` files into a list of event dicts `{ticker, type, date, ratio, metadata}`. (Verification: load MGLU3_events.bean, confirm desdobramento entries appear with correct ratio and date)
- [x] 10. Write `enrich_corporate_actions()`: for each B3 corporate action, find matching BRAPI event (±5 days, same ticker, same type). Fill ratio. Tag `^b3-brapi-enriched`. Flag no-match and date-drift >1 day. (Verification: MGLU3 desdobramento 2020-10-07 from BRAPI matches B3 entry from same period — ratio 4 filled in)
- [x] 11. Write `sanity_check_income()`: group B3 income entries by (ticker, type, date ±5 days), sum amounts, compare to BRAPI. Collect mismatches as warnings. (Verification: run against known data — grouped sum matches BRAPI amount for clean cases)
- [x] 12. Write `append_to_file()` and `rewrite_file()`: append deduplicates by `id` metadata field; rewrite replaces full file content. (Verification: run twice on same tmp.bean in append mode — no duplicate IDs in output files)
- [x] 13. Wire together: call parse → enrich → sanity-check → write all three files → print discrepancy report. (Verification: end-to-end run on real tmp.bean — three output files written, report printed to stdout)

## Slice 5: Update ledger includes
- [x] 14. In `main.bean` (or equivalent top-level file), replace `include "splits.bean"` with `include "corporate_actions.bean"` and add `include "income_events.bean"`. Confirm `prices/prices.bean` no longer includes `_events.bean` files. (Verification: `bean-check main.bean` passes with no errors about missing files)
- [x] 15. Rename `splits.bean` to `corporate_actions.bean`, update all existing `custom "split"` entries to `custom "desdobramento"` / `"grupamento"` / `"bonificacao"` as appropriate, and set correct ratios. (Verification: `bean-check main.bean` passes; `stock_split.py` no longer sees any `"split"` directives)

## Slice 7: Known gaps / deferred
- [ ] 18. Add `^b3` tag to corporate action entries in `importers/b3.py` — deferred because `_meta()` has no `tags=` param. Requires either extending `_meta()` or constructing the metadata dict manually with a `__tags__` key before passing to `data.Custom`.

## Slice 8: Yahoo Finance price service
- [x] 19. Write `plugins/yahoo_price_service.py` — mirrors `brapi_price_service.py` structure. Uses `yfinance`. Appends `.SA` suffix. Maps split ratios to desdobramento/grupamento/bonificacao. Fetches dividends and emits as `dividendo` (reference only). Tags `^yahoo`. Same output file format as BRAPI service. (Verification: run manually for MGLU3, inspect `prices/MGLU3_events.bean` — splits and dividends present with `^yahoo` tag)
- [x] 20. Update `plugins/price_updater.py` — swap `BrapiPriceUpdater` import and instantiation for `YahooPriceUpdater`. (Verification: Fava price update button runs without error)
- [x] 21. Update `reconcile_actions.py` — (a) make `load_events_bean()` tag-agnostic; (b) restrict enrichment matching to split-type events only (desdobramento/grupamento/bonificacao); (c) remove `sanity_check_income()` entirely. (Verification: reconcile run on real tmp.bean produces no income-related warnings)
- [x] 22. Install `yfinance` into venv: `.venv\Scripts\pip install yfinance>=0.2.0`. (Verification: `python -c "import yfinance; print(yfinance.__version__)"` succeeds)

## Slice 6: End-to-end verification
- [x] 16. Run full pipeline on real exports: extract → reconcile → bean-check. Confirm zero "Not enough lots" errors for the 7 target tickers (WEGE3, B3SA3, BBDC3, BBAS3, FLRY3, MGLU3, ITSA3). (Verification: `bean-check main.bean` output — no split-related errors for target tickers)
- [x] 17. Update `activeContext.md` with new pipeline flow and any remaining open items. (Verification: file updated and readable)

## Slice 9: B3SA3 / regex / all_history fixes (2026-07-09)
- [x] 23. Fix `BR_TICKER_RE` in `plugins/yahoo_price_service.py:30` — was `^[A-Z]{4}\d{1,2}$`, rejected B3SA3 (digit in prefix). Changed to `^[A-Z0-9]{4,5}\d{1,2}$`. (Verification: `_is_b3_ticker("B3SA3")` returns True; USD/BRL/CASH still rejected)
- [x] 24. Add `all_history` config flag to `YahooPriceUpdater` (default False). When True, includes every ticker that ever appeared in `Assets:Investment:*` (including fully-sold), not just `units > 0`. (Verification: behavioral test — B3SA3 included in all_history mode, skipped in default mode)
- [x] 25. Generate `prices/B3SA3_events.bean` via live Yahoo fetch to confirm the split lands. (Verification: file created, `desdobramento B3SA3 3` on 2021-05-17 present, matches corporate_actions.bean entry within ±5 day window)
- [ ] 26. Fill B3SA3 ratio in `corporate_actions.bean:23` — either re-run `reconcile_actions.py` against fresh tmp.bean containing B3SA3 entry, OR manually set ratio to `3` (optionally fix date to 2021-05-17). (Verification: bean-check no longer reports "Ratio is 0" for B3SA3)
- [ ] 27. Add `include "B3SA3.bean"` to `prices/prices.bean` — will be auto-added on next updater run with all_history=True. (Verification: `prices/prices.bean` contains the B3SA3 line, `bean-check` no longer reports missing glob)

## Slice 11: Repo reorganization — beans/ and scripts/ (2026-07-13)
- [x] 31. `git mv` root-level .bean files to `beans/`: accounts, commodities, transactions, corporate_actions, splits, income_events, manual_corrections. Leave `main.bean` and `tmp.bean` at root. (Verification: `ls beans/*.bean` shows 7 files; `ls *.bean` shows only main.bean, tmp.bean)
- [x] 32. `git mv prices/ beans/prices/`. (Verification: `ls beans/prices/prices.bean` exists; old `prices/` dir gone)
- [x] 33. Update `main.bean:49-55` include paths: `X.bean` → `beans/X.bean` (6 files) and `prices/prices.bean` → `beans/prices/prices.bean`. (Verification: `bean-check main.bean` finds all includes)
- [x] 34. Make yahoo prices_dir configurable: in `plugins/yahoo_price_service.py:144`, read `self.config.get("prices_dir", "prices")` instead of hardcoded `"prices"`. In `main.bean:28`, add config string to the fava-extension directive: `"{ 'prices_dir': 'beans/prices' }"`. Update brapi_price_service.py:171 hardcoded path to `"beans" / "prices"` (dormant, but don't let it silently break). (Verification: grep shows config key in yahoo; main.bean has config string; brapi hardcoded to beans/prices)
- [x] 35. `git mv reconcile_actions.py scripts/reconcile_actions.py`. Hardcode new paths (no REPO_ROOT refactor — user will refactor later): `base_dir / "prices"` → `base_dir / "beans" / "prices"`; output files → `base_dir / "beans" / "X.bean"`. Fix usage docstring to `python scripts/reconcile_actions.py`. (Verification: `python scripts/reconcile_actions.py --help` runs from repo root)
- [x] 36. Update `scripts/check_dividends.py:40`: `PRICES_DIR = os.path.join(REPO_ROOT, "prices")` → `os.path.join(REPO_ROOT, "beans", "prices")`. (Verification: script's startup print shows new path)
- [x] 37. Run `bean-check main.bean` (Verification: zero errors). Smoke-test `python scripts/check_dividends.py` and `python scripts/reconcile_actions.py --help`.
- [ ] 38. Commit and push. (Verification: `git log --oneline -1` shows the refactor commit on origin/main)

## Slice 12: International ticker support in price updater (2026-08-17)
- [x] 39. Support international tickers in `plugins/yahoo_price_service.py`: domicile inferred from ledger quote currency (BRL -> .SA, USD -> .L); `symbols` config map overrides per ticker; `_extract_holdings()` now returns quote currency per ticker; skip known currency codes (CURRENCY_CODES) and tickers whose Yahoo quote currency differs from the ledger. Removed now-dead `BR_TICKER_RE`/`_is_b3_ticker`. (Verification: unit-style run with VWRA/AVGS/IWVL in ledger — correct `.L` symbols and USD price lines)
- [x] 40. Add `symbols` config map to `main.bean` price_updater extension: `{'VWRA': 'VWRA.L', 'AVGS': 'AVGS.L', 'IWVL': 'IWVL.L'}`. (Verification: `bean-check main.bean` parses extension config)
- [x] 41. Add `commodity` directives for VWRA/AVGS/IWVL to `beans/commodities.bean` (International ETFs section). (Verification: `bean-check main.bean` no errors; commodities visible in Fava)
- [x] 42. Only index tickers with an actual price file in `prices.bean` — failed fetches (unknown symbol, network error, currency mismatch) no longer leave a dangling include. (Verification: simulated run — `include "BAD.bean"` absent when BAD.bean missing, GOOD.bean present)

## Slice 10: Fix "Not enough lots" — pre-booking split application (DEFERRED)
- [!] 28. Decide between Option B (bake splits into source .bean) vs Option C (standalone `scripts/apply_splits.py` pre-processor). Option C is leading candidate. See decision [011] for full research notes. User will return to this.
- [ ] 29. Scope the chosen approach against the 20 affected errors and the existing pipeline (import.py → reconcile_actions.py → bean-check).
- [ ] 30. Implement the chosen approach. (Verification: `bean-check main.bean` "Not enough lots" errors drop from 20 toward 0)

## Slice 13: Beangrow portfolio returns configuration (2026-08-18)
- [x] 43. Research current Beangrow configuration syntax and reconcile it with the local `fava-portfolio-returns` vendored implementation. (Verification: protobuf syntax and local parser confirmed.)
- [x] 44. Create `beangrow.pbtxt` with one exact investment block for each of the 56 investment asset accounts and broker-specific reporting groups. (Verification: config parses; all 56 ledger asset accounts are covered with no cash account accidentally treated as an investment.)
- [x] 45. Validate the configuration against `main.bean` and extract investment cash flows. (Verification: `bean-check main.bean` passes; 56 investments extract; BB, IBKR, Inter, and XP groups load.)
- [ ] 46. Refactor XP dividend/JCP/rendimento postings into security-specific income accounts so those distributions can be included accurately in Beangrow returns. (Verification: no duplicated XP distributions and per-security dividend flows appear in the returns reports.)
- [x] 47. Save the Beangrow research findings as a facts-only document in `docs/Beangrow - Configuration Research.md`. (Verification: document contains source links, observed versions, schema facts, ledger observations, and validation results without recommendations.)

## Slice 14: USD/BRL valuation price (2026-08-18)
- [x] 48. Add the `2026-08-18 price USD 5.2102 BRL` directive to `beans/manual_corrections.bean`. (Verification: `bean-check main.bean` passes and the directive is present.)

## Slice 15: Automated currency conversion prices (implemented and validated)
- [x] 49. Research Yahoo Finance currency-pair symbols, ledger currency discovery, and output implications. (Verification: findings and proposed decisions are recorded in `plan/spec_currency_conversion_prices.md` and `plan/decisions_currency_conversion_prices.md`.)
- [x] 49a. Confirm Beancount price orientation, automatic inverse rates, Fava conversion behavior, and the limits of `operating_currency`. (Verification: current Beancount/Fava documentation and source behavior are recorded in the feature specification.)
- [x] 49b. Select one generated `*.bean` file per currency pair under `beans/currencies/`. (Verification: output layout is recorded in the feature specification and decision log.)
- [x] 50. Implement the approved currency discovery and FX pair-fetching plan in `plugins/yahoo_price_service.py`. (Verification: complete criteria are in `plan/tasks_currency_conversion_prices.md`.)
