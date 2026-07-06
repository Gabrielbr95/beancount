# Decision Log

## [006] Yahoo Finance as primary price/events source; BRAPI retained as reference
- **Date:** 2026-07-05
- **Context:** BRAPI locks corporate events (splits, dividends) behind a paid tier.
  The free tier is not usable. Yahoo Finance provides the same data for free via
  `yfinance`, covers all required B3 tickers, and has no API key requirement.
- **Options Considered:**
  - A: BRAPI paid tier — better data quality, richer labels (JCP/rendimento distinction),
    ISIN codes. Expensive.
  - B: Yahoo Finance as primary — free, all tickers covered, `yfinance` is mature.
    Limitation: Yahoo dividends have no label field, so JCP/rendimento cannot be
    distinguished; all dividends emitted as `"dividendo"`.
  - C: Replace BRAPI entirely — cleaner, but loses the option to upgrade later.
- **Decision:** Option B + retain BRAPI code untouched.
- **Rationale:** Free tier covers the immediate need. BRAPI code stays as a
  dormant upgrade path — if the paid tier is ever activated, swap one import line
  in `price_updater.py`. JCP/rendimento distinction is a known limitation; income
  sanity-check in `reconcile_actions.py` will flag mismatches if it matters.

## [001] Directive naming: B3 terminology over source-prefixed names
- **Date:** 2026-07-05
- **Context:** BRAPI was emitting `"brapi-stock-dividend"` / `"brapi-cash-dividend"`.
  B3 importer was emitting `"split"` for all corporate action types. Neither matched
  the other, and neither was human-readable.
- **Options Considered:**
  - A: Keep source-prefixed names (`"brapi-stock-dividend"`, `"yahoo-split"`) — stable
    per-source but verbose and not meaningful to a Brazilian investor.
  - B: Use B3 Portuguese terminology (`"desdobramento"`, `"grupamento"`, `"bonificacao"`,
    `"dividendo"`, `"jcp"`, `"rendimento"`) — api-agnostic, matches domain vocabulary,
    readable in the ledger.
- **Decision:** Option B — B3 Portuguese terminology.
- **Rationale:** The ledger is a long-lived artifact. Source names couple it to the
  current data provider (BRAPI). Domain names survive a provider change. The user is
  a Brazilian investor; the terminology is natural. A `source:` tag (`^brapi`, `^b3`)
  preserves provenance without polluting the directive name.

## [002] Ratio sentinel value "0" for unenriched corporate actions
- **Date:** 2026-07-05
- **Context:** B3 export does not reliably provide split ratios. The importer emits
  corporate action directives before reconcile enriches them. We need to distinguish
  "ratio not yet known" from a valid ratio.
- **Options Considered:**
  - A: Omit the ratio field entirely — clean but `stock_split.py` would need
    a different code path to detect missing fields.
  - B: Use `"0"` as a sentinel — explicit, detectable, causes a loud error in
    `stock_split.py` if accidentally consumed before enrichment.
  - C: Use `"MISSING"` string — readable but requires string parsing in the plugin.
- **Decision:** Option B — `"0"` sentinel.
- **Rationale:** `stock_split.py` already validates `ratio > 0`. A zero ratio
  naturally triggers the existing error path with zero additional code. Loud failure
  by design.

## [003] _events.bean not included in ledger
- **Date:** 2026-07-05
- **Context:** `prices/TICKER_events.bean` contains rich BRAPI reference data for
  dividends and corporate actions. Previously these files were included in `prices.bean`
  and thus loaded by the ledger.
- **Options Considered:**
  - A: Keep in ledger — directives are passive `custom` entries, beancount ignores
    unknown custom types. Low risk.
  - B: Remove from ledger — cleaner separation, the ledger only loads what it
    actually acts on. Reference data stays reference data.
- **Decision:** Option B — not included in ledger.
- **Rationale:** Principle of least surprise. The ledger should only load what
  `stock_split.py` and other plugins consume. BRAPI events are inputs to
  `reconcile_actions.py`, not to the ledger runtime. Avoids future confusion if
  a plugin accidentally pattern-matches on these directives.

## [004] Reconcile script as post-processor of tmp.bean
- **Date:** 2026-07-05
- **Context:** beangulp `extract` writes all entry types to a single output file.
  We need three destination files. Options were: (A) multiple importer instances
  each filtered by type, (B) post-processor script, (C) bypass beangulp entirely.
- **Options Considered:**
  - A: Multiple importer instances — parses Excel 3×, fragile, awkward CLI.
  - B: Post-processor reads tmp.bean, routes + enriches + sanity-checks in one pass.
  - C: Bypass beangulp — loses dedup and CLI.
- **Decision:** Option B — single post-processor (`reconcile_actions.py`).
- **Rationale:** Consolidates routing, enrichment, and sanity-check into one place.
  beangulp does what it is good at (parsing, dedup). The post-processor does
  everything else. tmp.bean is kept for manual inspection.

## [005] Income event multi-line grouping: sum for sanity check, don't merge entries
- **Date:** 2026-07-05
- **Context:** B3 sometimes records a single dividend event across multiple rows
  (e.g. 300 shares + 200 shares). BRAPI has one record for the event.
- **Options Considered:**
  - A: Merge B3 rows into one entry — loses row-level traceability, complicates IDs.
  - B: Keep rows separate in income_events.bean; sum B3 amounts when comparing
    to BRAPI in the sanity check.
- **Decision:** Option B — keep rows separate, sum for comparison only.
- **Rationale:** Traceability back to B3 source row IDs is preserved. The sanity
  check is still meaningful. No user-visible difference in the ledger.
