# Specification

## Objective
Extend `plugins/yahoo_price_service.py` so it fetches daily foreign-exchange
conversion prices for currencies actually used by the ledger. For each used
currency, provide prices quoted in BRL and in USD, using Beancount's normal
`price BASE RATE QUOTE` directive orientation.

## Approved Implementation Direction
- Implement this inside `plugins/yahoo_price_service.py`, reusing its existing
  yfinance dependency, date handling, overlap window, generated-file pattern,
  and `RunSummary` reporting.
- Provide direct conversion paths to both BRL and USD rather than depending on
  arbitrary multi-hop conversion. This supports Fava's one-step `Converted to
  BRL` and `Converted to USD` views.
- Deduplicate the USD/BRL pair: write one authoritative orientation and rely on
  Beancount's automatically generated inverse.

## Current Findings
- The updater already uses `yfinance` and Yahoo Finance symbols for security
  price history.
- Yahoo Finance exposes currency pairs as symbols ending in `=X`; live checks
  confirmed `USDBRL=X`, `BRLUSD=X`, and `EURBRL=X` return `instrumentType=\"CURRENCY\"`.
- Yahoo's chart metadata identifies the quote currency. For example,
  `USDBRL=X` reports `currency=BRL` and `BRLUSD=X` reports `currency=USD`.
- The current ledger loader contains these currency codes in postings, costs,
  prices, or price directives: `ARS`, `BRL`, `GBP`, `SGD`, and `USD`.
- Excluding identity pairs, the current requested output is eight pairs:
  `ARSBRL`, `GBPBRL`, `SGDBRL`, `USDBRL`, `ARSUSD`, `BRLUSD`, `GBPUSD`, and
  `SGDUSD`.
- A Beancount `price` directive is `price BASE RATE QUOTE`, meaning one unit of
  BASE is worth RATE units of QUOTE. For example:
  `2026-08-18 price USD 5.2042 BRL`.
- Beancount's price map automatically creates inverse lookup rates. Both
  directions do not need separate directives; recording both can create
  redundant or conflicting same-date data.
- Fava's `Converted to X` conversion uses prices from the ledger. For a
  position held at cost, Fava can convert via the cost currency when a direct
  asset-to-X price is absent, and Fava also supports chained conversions.
- `operating_currency` controls displayed report columns; it does not itself
  perform valuation or convert the portfolio.
- The ledger already enables `beancount.plugins.implicit_prices`, which helps
  populate prices implied by transaction costs but does not replace current
  market prices or FX rates.

## Core Requirements
1. Discover currencies from the loaded ledger rather than from the investment
   ticker list. Do not treat security symbols, bond identifiers, or other
   commodities as currencies.
2. For every discovered currency other than BRL, fetch a `CURRENCYBRL=X`
   series. For every discovered currency other than USD, fetch a `CURRENCYUSD=X`
   series. Emit one orientation per pair only; rely on Beancount's inverse
   lookup for the reverse direction.
3. Write each successful daily close as a Beancount price directive:
   `YYYY-MM-DD price BASE RATE QUOTE`.
4. Preserve existing historical data and use the updater's overlap-window and
   full-refresh behavior for currency data as well as asset data.
5. Validate Yahoo's reported instrument/quote currency before writing data.
   A failed, missing, or incompatible pair must produce a visible warning or
   error and must not write misleading directives.
6. Keep generated FX prices separate from security price files and avoid adding
   FX files to the security ticker index accidentally.
7. Prevent duplicate/conflicting directives with the manually added
   `2026-08-18 price USD 5.2102 BRL` in `beans/manual_corrections.bean`.

## Valuation Behavior
- To view the portfolio in BRL, use Fava's `Converted to BRL` conversion with
  security prices in their native quote currencies plus FX prices into BRL.
- To view it in USD, use `Converted to USD` with the corresponding native quote
  prices plus FX prices into USD.
- FX prices convert currencies; they do not value a security whose latest
  market price is missing. Market-value net worth therefore requires both
  security prices and currency conversion prices.
- Historical valuation requires FX prices on or before the valuation date, just
  as security prices do. A current FX quote cannot correctly value an older
  portfolio snapshot.

## Proposed Output
- Generate one dedicated Beancount file per stored currency pair under
  `beans/currencies/`, for example `beans/currencies/USD_BRL.bean` and
  `beans/currencies/GBP_USD.bean`.
- Each pair file contains only that pair's dated `price` directives and a
  generated source header.
- Ensure every generated pair file is included exactly once from the ledger.
  The existing security `beans/prices/prices.bean` index should remain a
  security-file index.
- Decide during implementation whether the one-off manual USD/BRL directive is
  migrated into the generated USD/BRL pair file or retained with explicit
  de-duplication. Do not silently leave two same-date USD/BRL prices.

## Planned Plugin Design
1. Add a ledger-currency discovery helper. Inspect posting units, posting costs,
   posting prices, and `Price` directives; retain only known currency codes
   from `CURRENCY_CODES`. Do not use investment commodity symbols as the
   currency list.
2. Add deterministic pair planning. For each used currency, create a direct
   pair to BRL unless it is BRL, and a direct pair to USD unless it is USD.
   Collapse the two requests for the BRL/USD relationship into the preferred
   `USD → BRL` Yahoo pair.
3. Add a Yahoo FX-symbol helper that maps `(base, quote)` to
   `BASEQUOTE=X`, with a clear validation error for unsupported/non-three-letter
   codes.
4. Add a currency-history fetcher. Use `yf.Ticker(pair_symbol).history()` with
   `period=\"max\"` for a new pair and the existing overlap-window start/end
   behavior for an existing pair. Keep daily `Close` values and skip missing
   values.
5. Validate the Yahoo response before writing: instrument type must be currency
   when available, the symbol must match the requested pair, and the reported
   quote currency must equal the requested quote. A failed pair is reported and
   does not produce price directives.
6. Merge each pair's history into its own generated file under
   `beans/currencies/`, preserving dates outside the overlap window and
   replacing overlapping values only when the fetched data is valid.
7. Include every generated pair file exactly once while keeping
   `beans/prices/prices.bean` a security-file index. Migrate or remove the
   existing manual USD/BRL directive so the pair file is the single source for
   that pair.
8. Extend the run summary with fetched pairs, skipped identity pairs, failed
  pairs, and the generated pair files.

## Out of Scope
- No exchange-rate provider other than Yahoo Finance/yfinance.
- No intraday or bid/ask FX data; use daily close data only.
- No conversion of security prices into a second reporting currency. Security
  files continue to use their ledger quote currencies.
- No changes to the BRAPI price service.

## User Interaction
- The existing Fava price-updater action remains the trigger.
- A successful run updates security files and the generated pair files under
  `beans/currencies/`.
- The run summary reports fetched pairs, skipped identity pairs, and failed
  pairs with enough detail to diagnose Yahoo symbol/data problems.
- The implementation should be testable without network access by injecting or
  mocking the yfinance ticker/history response.
