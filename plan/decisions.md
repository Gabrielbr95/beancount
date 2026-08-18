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

## [007] Custom directive numeric values must be bare, not quoted
- **Date:** 2026-07-09
- **Context:** Per beancount's custom-directive syntax
  (`2014-07-09 custom "budget" "..." TRUE 45.30 USD`), values are typed: strings
  quoted, numbers/booleans/amounts bare. `yahoo_price_service.py` and
  `brapi_price_service.py` were wrapping the numeric ratio/amount/rate/factor in
  `_quote()`, emitting `"4"` instead of `4`. Beancount parses this as a `str`,
  not a `Decimal` — silent type mismatch for any downstream query.
- **Options Considered:**
  - A: Keep quoted — "works" because `Decimal(str_value)` accepts both. But
    semantically wrong and breaks typed queries on custom directives.
  - B: Emit bare numbers per beancount syntax. Strings (ticker, source, metadata
    key=value pairs) stay quoted.
- **Decision:** Option B — bare numbers in all three writers:
  `yahoo_price_service.py` (ratio line 287, amount line 310),
  `brapi_price_service.py` (rate line 327, factor line 352),
  `reconcile_actions.py` (enrichment replacement, line 244).
- **Rationale:** Correctness per the language spec. `stock_split.py` line 33
  (`Decimal(entry.values[1].value)`) is robust to either form, so no consumer
  breakage. The regexes `_EVENT_RE` and `_CORP_DIRECTIVE_RE` were updated to
  accept both quoted (legacy) and bare (new) ratios so reconcile keeps working
  against existing `*_events.bean` files until they are regenerated.
- **Migration:** Re-run the Yahoo/BRAPI price services to regenerate
  `prices/*_events.bean` with bare numbers, then `reconcile_actions.py --rewrite`.

## [009] BR_TICKER_RE regex fix — B3SA3 was silently rejected
- **Date:** 2026-07-09
- **Context:** `plugins/yahoo_price_service.py:30` used `^[A-Z]{4}\d{1,2}$` to
  validate B3 tickers. B3SA3 (the exchange's own ticker) has a digit at position
  2 ("B3" prefix), so it failed validation and was skipped as "unsupported ticker".
  This caused `prices/B3SA3.bean` and `prices/B3SA3_events.bean` to never be
  generated — even while B3SA3 was held. The user had been chasing "yfinance
  can't find B3SA3" for a while; yfinance finds it fine under `B3SA3.SA`, the
  bug was the local validator rejecting it before yfinance was ever called.
  Verified B3SA3 was the ONLY affected ticker of 28 tested.
- **Options Considered:**
  - A: Whitelist B3SA3 as a special case — fragile, hides the real issue.
  - B: Broaden regex to `^[A-Z0-9]{4,5}\d{1,2}$` — accepts alphanumeric prefixes
    (B3SA3, future tickers with digits), still rejects USD/BRL/CASH.
- **Decision:** Option B — `^[A-Z0-9]{4,5}\d{1,2}$`.
- **Rationale:** B3 ticker format allows alphanumeric prefixes; the original
  4-letter assumption was wrong. Still rejects 3-letter currency codes and garbage.

## [010] all_history config flag for price updater
- **Date:** 2026-07-09
- **Context:** `YahooPriceUpdater` only updated tickers with `units > 0` (currently
  held). Fully-sold tickers (e.g. B3SA3 after full sale) lost their `*_events.bean`
  updates. Historical corporate actions affect past lot cost-basis forever, so
  sold tickers still need event tracking. The flag was requested to support this
  without changing default behavior.
- **Options Considered:**
  - A: Always generate events for all historical tickers — slow on every run,
    breaks the "only update what I hold" optimization for prices.
  - B: Add `all_history` config flag (default False, current behavior preserved).
    When True, includes every ticker that ever appeared in `Assets:Investment:*`
    postings (key presence in holdings dict = "was traded"), even if net balance
    is 0.
- **Decision:** Option B — `all_history` flag, default False.
- **Rationale:** Preserves the fast default (current holdings only) while
  allowing a periodic "full history sweep" run. Toggled via main.bean:
  `2010-01-01 custom "fava-extension" "plugins.price_updater" "{'all_history': True}"`
- **Implementation Note:** The include logic in `_extract_holdings` only adds
  keys for tickers with real postings, so key existence is sufficient evidence
  of trade history (no need to check `units != 0` — that was the original
  wrong approach and failed for fully-sold tickers with net-zero balance).

## [011] stock_split plugin runs AFTER booking — design-breaking limitation
- **Date:** 2026-07-09
- **Context:** Discovered during diagnosis of "Not enough lots to reduce" errors
  (20 of 39 bean-check errors). The `stock_split.py` plugin retroactively
  adjusts historical postings (e.g. 300 ITSA3 @ 10.99 → 315 ITSA3 @ 10.466
  after a 1.05 bonificação), but beancount's loader pipeline runs `booking.book()`
  BEFORE `run_transformations()` (where plugins execute). So the booking engine
  makes FIFO lot-matching decisions on the ORIGINAL unmodified 300 shares, then
  the plugin transforms them — too late. A subsequent sell of 300 fails because
  booking saw only 299 after earlier sells of 1+14.
- **Research Findings (Option 2 — pre-booking plugin):**
  - The beancount loader hardcodes: parse → booking → plugins → validate.
  - `PLUGINS_PRE`/`PLUGINS_POST` refer to ordering among plugins, NOT relative
    to booking. DeepWiki's claim that PLUGINS_PRE runs "before booking" is
    wrong for beancount 3.x — verified directly in `loader.py:_load` (lines
    605-606 booking, then 661+ plugins).
  - `plugin_processing_mode` ("raw" vs "default") only changes which plugins
    run inside the transform step, does not move them before booking.
  - Martin Blais (beancount maintainer) acknowledged in 2020: "Currently it
    is not possible to run such a plugin [pre-booking] because plugins run
    after the booking process has completed." Pre-booking plugins are a
    future proposal, never implemented.
  - The only way to run pre-booking: bypass `loader.load_file()` and call
    `parser.parse_file()` → `my_plugin()` → `booking.book()` manually. This
    breaks Fava (which calls `loader.load_file()` internally with no pre-booking
    hook). `parser.parse_file` also does not resolve `include` directives,
    requiring manual recursive include resolution.
  - Bonus: tested `booking_method "NONE"` — it produces a DIFFERENT error
    ("Too many missing numbers for currency group 'BRL'") because empty-lot
    `{}` reduces can't interpolate without FIFO matching. Trades 20 "not
    enough lots" errors for 20 "too many missing numbers" errors. Confirms
    the comment in `main.bean:8-10` was right to reject NONE.
- **Options Considered (for fixing the 20 errors):**
  - A: Pre-booking plugin — NOT VIABLE. Breaks Fava integration, requires
    reimplementing include resolution, not a supported beancount pattern.
  - B: Bake splits into source .bean files — rewrite `transactions.bean` buys
    to post-split quantities/costs, delete bonificação entries. Booking then
    sees correct numbers from the start. Loses 1:1 correspondence with broker
    export (300 → 315 in the file).
  - C: Standalone pre-processing script — `scripts/apply_splits.py` reads
    `corporate_actions.bean`, transforms `transactions.bean` in-place (adjusts
    buy quantities/costs and sell quantities), outputs clean bean file. Run
    as a pipeline step before `bean-check`. Same approach as `reconcile_actions.py`.
- **Decision:** DEFERRED — no decision yet. User will return to this.
- **Rationale:** This is a design-level choice affecting the entire pipeline.
  Option C is the leading candidate (matches Script-tier philosophy and
  existing pipeline shape) but needs scoping before committing.


- **Date:** 2026-07-09
- **Context:** `reconcile_actions.py` marked enriched corporate-action entries
  with `^b3-yahoo-enriched` (a beancount LINK). Testing revealed `^link` is
  **invalid grammar on custom directives** — `bean-check` rejects it as
  "unexpected LINK". This was latent: the enrichment path was unreachable before
  the [007] regex fix, so the bug never surfaced.
- **Options Considered:**
  - A: Keep the `^link` tag — invalid, rejected by `bean-check`.
  - B: Use a `#tag` instead — also invalid on custom directives (same grammar rule).
  - C: Use a metadata key `yahoo-enriched: TRUE` — beancount-valid on all entries.
- **Decision:** Option C — metadata key `yahoo-enriched: TRUE` inserted below
  the directive line in `reconcile_actions.py` (replaces lines 251-253).
- **Rationale:** Valid beancount grammar, `bean-check` passes, preserves the
  "already enriched" marker for re-runs and audit. Note: the `^yahoo` / `^brapi`
  tags in `prices/*_events.bean` are also technically invalid, but those files
  are not included in `main.bean` (decision [003]), so `bean-check` never sees
  them. Left as-is for now; flagged for future cleanup if those files ever get
  included.

## [013] IBKR integration importer: uabean
- **Date:** 2026-08-17
- **Context:** The user will integrate Interactive Brokers into the Beancount
  ledger and needs an importer. Research (via subagents, 2026-08-17) covered the
  full IBKR importer landscape: drnuke-bean, uabean, reds_importers (v2-only for
  stable), tarioch/beancounttools, alens-importers, and the `ibflex` building
  block. The user also plans Wise and Binance integration in the future.
- **Options Considered:**
  - A: drnuke-bean — most complete, actively maintained, v3/beangulp, exact lot
    matching. Heavier: Python >=3.12, more deps (loguru, smart_importer,
    diskcache), Swiss-flavored defaults to configure.
  - B: uabean — v3/beangulp, MIT, offline-capable (manual Flex XML export),
    fewest deps (beangulp, ibflex, openpyxl, xlrd, requests, python-dateutil).
    Also ships `uabean-wise-downloader` (relevant to the future Wise plan).
  - C: reds_importers — most-cited but v3 port is explicitly "not ready".
  - D: Roll own thin importer on `ibflex` — full control, most work.
- **Decision:** Option B — uabean.
- **Rationale:** Fits the corporate Windows/no-admin, local-first constraint
  (manual Flex XML export means zero connectivity at import time). Fewest
  dependencies, MIT license, already beangulp-native for the v3 ledger. Wise
  downloader is a bonus for the stated future plan. Known caveats accepted:
  `beangulp` pinned to git master (may override the installed 0.2.0 — test
  before committing), and ibflex pinned to a git commit. Binance will need a
  separate importer (not in uabean); revisit when needed.
- **Implementation Notes:** Venv (Python 3.14.6) already has beancount 3.2.3,
  beangulp 0.2.0, beanquery 0.2.0, smart_importer 1.2, diskcache, requests,
  python-dateutil. Missing for uabean: `ibflex[web]` (pinned commit),
  `openpyxl`, `xlrd`. Per research consensus: use Flex Web Service, STRICT/date
  lot matching, per-symbol sub-accounts, `{{total cost}}` for fractional shares.
