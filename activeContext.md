# Active Context

## Resume Here
- **Tier:** Script
- **Current Slice:** Automated currency conversion prices (Slice 15) — implementation complete and validated.
- **Current Task:** `plan/tasks.md` task 50 — complete.
- **Next Action:** Review the commit result and remote status. The generated FX files under `beans/currencies/` are part of the implementation and must be retained.

## Completed This Session
- Added `2026-08-18 price USD 5.2102 BRL` to `beans/manual_corrections.bean`.
- Verified the directive with `bean-check main.bean` and `git diff --check`.
- Recorded the completed price task as task 48 in `plan/tasks.md`.
- Researched Yahoo `BASEQUOTE=X` currency symbols and the current ledger currency set.
- Added a feature specification, proposed decisions, and implementation task breakdown for automated FX prices. No application code was changed.
- Confirmed from current Beancount source and Fava documentation that `price BASE RATE QUOTE` entries feed the price map, inverse rates are generated automatically, and Fava's `Converted to X` conversion is the portfolio-valuation mechanism.
- Implemented Yahoo FX retrieval in `plugins/yahoo_price_service.py`; it discovers ledger currencies, fetches direct BRL/USD pairs, writes one file per pair under `beans/currencies/`, and reports pair-level failures.
- Added the `beans/currencies/*.bean` include, removed the one-off manual USD/BRL directive, generated seven current pair files, and added offline tests.

## Blockers / Open Questions
- None blocking. The working tree contains several intentional but uncommitted Beangrow/configuration and documentation changes from the preceding work.
- Beangrow task 46 remains pending: refactor generic XP dividend/JCP/rendimento postings into security-specific income accounts.
- FX decisions in `plan/decisions_currency_conversion_prices.md` were accepted as the implementation direction on 2026-08-18.
- Do not emit both orientations of the same FX pair; store one authoritative orientation and rely on Beancount's inverse lookup.
- Generate one `*.bean` file per stored currency pair under `beans/currencies/`; do not use a combined FX file.
- The generated pair files are currently uncommitted and contain Yahoo history through 2026-08-18.

## Read These First
- `beans/manual_corrections.bean`: newly added USD/BRL price directive.
- `plan/tasks.md`: current task state, especially Slices 13–14.
- `beangrow.pbtxt`: uncommitted Beangrow configuration baseline.
- `docs/Beangrow - Configuration Research.md`: facts-only research supporting the configuration.
- `plan/decisions.md`: durable Beangrow decision and other recent decisions.
- `plan/spec_currency_conversion_prices.md`: FX requirements, findings, scope, and open migration point.
- `plan/decisions_currency_conversion_prices.md`: proposed Yahoo/source, discovery, and output decisions.
- `plan/tasks_currency_conversion_prices.md`: implementation and verification sequence.
- `plugins/yahoo_price_service.py`: FX discovery, pair planning, retrieval, validation, merge, and output implementation.
- `tests/test_yahoo_price_service.py`: offline FX helper tests.
- `beans/currencies/*.bean`: generated Yahoo currency-pair price histories.
