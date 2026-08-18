# Implementation Plan

## Slice 1: Discover currencies and plan FX pairs
- [x] 1. Inspect the loaded ledger and identify the current used currency set. (Verification: current set recorded as `ARS`, `BRL`, `GBP`, `SGD`, `USD`.)
- [x] 2. Add a helper in `plugins/yahoo_price_service.py` that discovers currency codes from posting units, costs, prices, and `Price` directives while filtering through `CURRENCY_CODES`. (Verification: fixtures include cash currencies and exclude commodities such as `AVGS`, `VWRA`, and `EIMI`.)
- [x] 3. Add deterministic pair planning: each used currency gets a direct BRL pair unless it is BRL, and a direct USD pair unless it is USD. (Verification: current ledger plans eight logical target pairs.)
- [x] 4. Deduplicate the USD/BRL relationship and select one stored orientation, preferably `USD → BRL`; rely on Beancount for the inverse. (Verification: no plan contains both `USD/BRL` and `BRL/USD` as separate generated series.)

## Slice 2: Fetch and validate Yahoo FX history
- [x] 5. Add a helper mapping `(base_currency, quote_currency)` to Yahoo's `BASEQUOTE=X` symbol. (Verification: `("USD", "BRL")` maps to `USDBRL=X`; invalid codes fail loudly.)
- [x] 6. Add FX history retrieval using the existing initial `period="max"` and incremental overlap-window behavior. (Verification: live run generated all seven current pair files.)
- [x] 7. Convert valid daily `Close` values to `Decimal` price points and skip null/NaN rows. (Verification: offline test covers dated closes and NaN filtering.)
- [x] 8. Validate Yahoo metadata when available: currency instrument, requested base/quote symbol, and quote currency. (Verification: live run completed with no metadata errors.)
- [x] 9. Add pair-level failure reporting without aborting unrelated security or FX pairs. (Verification: errors are stored with the `FX BASE/QUOTE` pair label.)

## Slice 3: Generate ledger-readable FX output
- [x] 10. Add a parser/merge path for one generated file per pair under `beans/currencies/`, preserving dates outside the overlap window and replacing valid overlapping rates. (Verification: reruns are stable and retain historical FX data independently for each pair.)
- [x] 11. Write directives as `YYYY-MM-DD price BASE RATE QUOTE` with generated metadata identifying the Yahoo FX source. (Verification: generated output parses with Beancount.)
- [x] 12. Ensure every generated pair file is included exactly once and remains separate from the security `beans/prices/prices.bean` index. (Verification: `bean-check main.bean` passes and the security index contains no currency pseudo-tickers.)
- [x] 13. Migrate or remove the manually added `2026-08-18 price USD 5.2102 BRL` so the generated USD/BRL pair file is the sole source for that same-date pair. (Verification: no duplicate/conflicting USD/BRL price remains.)

## Slice 4: Verify portfolio conversion behavior
- [x] 14. Add offline tests for currency discovery, pair deduplication, symbol mapping, close extraction, pair-file formatting, and metadata validation. (Verification: `python -m unittest tests.test_yahoo_price_service` passes.)
- [x] 15. Run a controlled live Yahoo smoke test for all current logical pairs. (Verification: seven pair files generated with no FX errors.)
- [x] 16. Verify the Beancount conversion path used by Fava for BRL and USD using generated FX prices and native security prices. (Verification: Beancount's conversion API resolved USD→BRL, BRL→USD, GBP→BRL, and GBP→USD from the generated price map.)
- [x] 17. Run `bean-check main.bean` and document the final updater behavior. (Verification: ledger validates and the resume documentation identifies the `beans/currencies/` pair-file workflow.)
