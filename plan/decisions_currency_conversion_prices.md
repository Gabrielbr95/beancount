# Decision Log

## [001] Use Yahoo Finance currency-pair symbols
- **Date:** 2026-08-18
- **Status:** Accepted for implementation.
- **Context:** The Yahoo price updater already depends on `yfinance`, and the
  requested conversion prices must be produced by the same recurring workflow.
- **Options Considered:**
  - A: Add a second FX provider or package — introduces another dependency and
    another failure/data-quality model.
  - B: Use Yahoo Finance `BASEQUOTE=X` pairs through the existing `yfinance`
    dependency — reuses the current transport and output conventions.
- **Decision:** Proposed option B.
- **Rationale:** Live Yahoo chart responses confirmed the required `=X` symbols
  identify themselves as currency instruments and report the quote currency.

> **Approval:** User accepted the direct Yahoo FX-pair approach on 2026-08-18.

## [002] Discover currencies from ledger amounts, not tickers
- **Date:** 2026-08-18
- **Status:** Accepted for implementation.
- **Context:** The ledger contains security symbols that resemble codes but are
  not currencies. The updater must fetch only currencies actually used in
  postings, costs, prices, or price directives.
- **Options Considered:**
  - A: Use the existing `CURRENCY_CODES` set as the complete request list —
    simple but would fetch currencies that are not present in this ledger.
  - B: Inspect loaded Beancount amounts and filter against known currency codes
    — follows the ledger and avoids treating security commodities as currencies.
- **Decision:** Proposed option B, retaining the code set as a classification
  guard rather than as the fetch list.
- **Rationale:** The current ledger has `ARS`, `BRL`, `GBP`, `SGD`, and `USD`,
  while its investment commodities include many non-currency identifiers.

> **Approval:** User accepted the ledger-driven currency set on 2026-08-18.

## [003] Store FX prices in a dedicated generated file
- **Date:** 2026-08-18
- **Status:** Accepted for implementation.
- **Context:** `prices.bean` is currently generated as an index of security
  price files, while currency prices are ledger-wide conversion data.
- **Options Considered:**
  - A: Append FX directives to `prices.bean` — minimal file count but mixes an
    index with ledger directives and risks updater overwrite behavior.
  - B: Generate `currencies.bean` and include it once from the ledger — keeps
    roles separate and gives one stable place for all FX pairs.
- **Decision:** Proposed option B.
- **Rationale:** It avoids confusing FX pairs with security tickers and makes
  duplicate handling with the current manual USD/BRL price explicit.

> **Approval:** User accepted the dedicated generated FX output as part of the
> implementation plan on 2026-08-18.

> **Superseded by [006]:** The output remains separate from security prices, but
> it will use one file per pair under `beans/currencies/`, not one combined FX
> file.

## [004] Emit one price orientation per currency pair
- **Date:** 2026-08-18
- **Status:** Accepted for implementation.
- **Context:** Beancount's price map automatically creates inverse rates for
  every recorded price pair.
- **Options Considered:**
  - A: Write both `BASE QUOTE` and `QUOTE BASE` directives — redundant and can
    create inconsistent rates.
  - B: Write one orientation and use Beancount's generated inverse — smaller,
    clearer price database.
- **Decision:** Proposed option B.
- **Rationale:** Beancount documents and implements inverse lookup in its price
  map. One authoritative daily rate avoids duplicate same-date FX data.

> **Approval:** User accepted direct conversion paths with one stored
> orientation per pair on 2026-08-18.

## [005] Use Fava conversion for portfolio valuation
- **Date:** 2026-08-18
- **Status:** Accepted for implementation.
- **Context:** `operating_currency` declarations do not perform market-value
  conversion. Fava has an explicit `Converted to X` report conversion that uses
  ledger prices and can convert via cost currencies or chained conversions.
- **Options Considered:**
  - A: Add more `operating_currency` declarations — affects report columns but
    does not solve valuation.
  - B: Record native security prices plus FX `price` directives and use Fava's
    conversion selector — uses Beancount's price database as intended.
- **Decision:** Proposed option B.
- **Rationale:** It values securities in their native quote currencies first and
  then converts the resulting portfolio value to one selected currency.

> **Approval:** User accepted this valuation workflow on 2026-08-18.

## [006] Store one generated file per currency pair
- **Date:** 2026-08-18
- **Status:** Accepted for implementation.
- **Context:** FX data is generated independently for each Yahoo currency pair
  and should remain easy to inspect, update, and include selectively.
- **Options Considered:**
  - A: One combined `currencies.bean` file — fewer files but mixes all pair
    histories and makes pair-level inspection or recovery less convenient.
  - B: One `*.bean` file per pair under `beans/currencies/` — clear ownership,
    pair-level updates, and straightforward generated-file validation.
- **Decision:** Option B.
- **Rationale:** The user explicitly wants one Beancount file per currency pair.
  Pair files also prevent one failed pair from making the entire FX output
  appear changed.
