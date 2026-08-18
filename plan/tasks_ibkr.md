# Implementation Plan

## Slice 1: Vendor the IBKR importer and install minimal deps
- [x] 1. Fetch `src/uabean/importers/ibkr.py` and `src/uabean/importers/mixins.py` from the uabean repo (MIT). Copy `ibkr.py` → `importers/ibkr.py` and inline/copy the `IdentifyMixin` (e.g. `importers/ibkr_mixins.py` or adapt the import). Keep the MIT attribution header. (Verification: `importers/ibkr.py` imports resolve locally — `python -c "from importers.ibkr import Importer"` succeeds after fixing the mixin import path)
- [x] 2. Install only `ibflex` into the venv: `pip install ibflex`. (Verification: `python -c "from ibflex import Types, parser; from ibflex.enums import BuySell, CashAction, OpenClose, Reorg"` succeeds)
- [x] 3. Regression check the existing pipeline: `.venv/bin/python import.py extract export/ > /dev/null` still runs without errors. (Verification: no import/dependency errors, exit code 0)
- [x] 4. Confirm the vendored importer identifies a Flex XML sample via `beangulp.testing.main` (module `if __name__ == "__main__"` harness). (Verification: test harness runs, identifies a `<FlexQueryResponse` XML; full extract matches upstream's expected fixture when existing holdings are fed in)

## Slice 2: Create the Flex Query and obtain a real XML export
- [ ] 5. User creates ONE Activity Flex Query in IBKR Client Portal (Performance & Reports → Flex Queries) with the exact sections/options from the spec (Trades: Executions + Closed Lots; Cash Transactions: all dividend/tax/fee/interest/deposit options + Detail; Cash Report: Currency Breakout; Corporate Actions: Detail). Run it and download the XML to `export/`. (Verification: exported file starts with `<FlexQueryResponse` and contains Trades/CashTransactions/CashReport/CorporateActions sections)
- [x] 6. Extract the real file with the vendored importer (via a throwaway script, before CONFIG wiring). (Verification: output contains Transactions and Balance entries; any RuntimeError from unexpected corporate-action structures is captured for manual handling) — DONE with `Beancount-uabean-2021.xml`: trades EIMI/IWDA + deposits + cash balance emitted cleanly.

## Slice 3: Wire the importer into the project
- [x] 7. Register the IBKR importer in `import.py` CONFIG (decision [006]) — import from `importers.ibkr`, add `IBKRImporter(...)` with the account config from the spec, UTF-8 stdout reconfigure already present. (Verification: importing `import.py` as a module yields a CONFIG with B3Importer, PluggyImporter, Importer; the IBKR importer's identify() returns True on a real Flex XML) — DONE.
- [ ] 8. Add commodity directives for any IBKR symbols seen in the first extraction (e.g. EIMI, IWDA) to `beans/commodities.bean`, matching the existing B3-ticker declaration style. (Verification: `bean-check main.bean` passes with the new commodities)

## Slice 4: First full-history import and review
- [ ] 9. Run the full workflow on the real full-history XMLs (2021-2026): extract → review `tmp.bean` → complete single-leg deposit/withdrawal counterparts with correct bank/transfer accounts → run `bean-check`. (Verification: no unbalanced-transaction errors remain; deposits/withdrawals have explicit counterparts)
- [ ] 10. Verify cost basis: compare ledger holdings against the IBKR Flex report (positions + cost basis) for a sample of symbols. (Verification: match within rounding tolerance; flag any AVERAGE-vs-lot mismatch for decision review)
- [ ] 11. Verify balance directives: the importer emits Balance entries from the Cash Report (dated `toDate + 1`); check `bean-check` passes and the asserted cash matches the IBKR statement. (Verification: `bean-check` clean; any balance mismatch is investigated — likely a missing deposit/withdrawal or FX leg)

## Slice 5: End-to-end verification and docs
- [ ] 12. Document the recurring workflow in `activeContext.md` / relevant docs: export → extract → complete deposits → bean-check. (Verification: steps reproducible from the doc alone)
- [ ] 13. Commit the integration (importers/ibkr.py, importers/ibkr_mixins.py, import.py CONFIG, commodities, decisions). (Verification: `git log` shows the commit; `bean-check` clean on a fresh clone/checkout)