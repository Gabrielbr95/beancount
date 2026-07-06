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
