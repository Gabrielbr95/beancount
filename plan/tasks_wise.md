# Implementation Plan — Wise Importer

Tier: Script. Follows the house pattern of `importers/pluggy.py` (plain `beangulp.Importer` + stdlib csv). Decisions in `plan/decisions_wise.md`.

## Slice 1: Importer scaffold + file handling
- [x] 1. Write `importers/wise.py`: `WiseImporter(beangulp.Importer)` with `identify()` matching `^statement_\d+_[A-Z]{3}_\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}\.csv$`, `account()` derived from currency parsed out of the filename (`Assets:Bank:Wise:<CURRENCY>`), `name` = "Wise Importer". (Verification: `python -c` instantiate + call `identify()` on the 9 sample filenames → True only for Wise files; `account()` returns `Assets:Bank:Wise:SGD` for the SGD file.)
- [x] 2. Add `read_rows()` helper using `csv.DictReader` (utf-8, header named the 23 columns), returning list of row dicts. Header-only files return `[]`. Guard: raise a loud error if a known column (e.g. `TransferWise ID`) is missing. (Verification: SGD file yields 206 rows; EUR file yields 0 rows; a file with a mangled header raises.)
- [x] 3. Implement `date()` (max row date, parsed day-first `DD-MM-YYYY`) and `filename()` (e.g. `2026-08-18.wise.bean`). (Verification: `date()` on SGD file returns 2026-07-23; `filename()` is date-based.)

## Slice 2: Plain row → transaction (CARD / DEPOSIT / TRANSFER)
- [x] 4. Implement `_build_txn(row, currency, account, filepath, lineno)`: Transaction with `id: wise-<TransferWise ID>`, `source: "wise"`, `^wise` tag, payee = Merchant or Payee/Payer Name (fallback), narration = Description, metadata for exchange rate / exchange-to amount / card last-4 / payment reference when present. (Verification: unit test — a CARD row yields a Transaction with the right id, tag, narration, metadata.)
- [x] 5. Counterpart logic: outflows (`Amount < 0` / DEBIT) → `Expenses:Uncategorized:Wise`; inflows → `Income:Uncategorized:Wise`; both postings balanced. Sign/type consistency check logs a warning on `(Amount<0) != (Type==DEBIT)`. (Verification: unit test — CREDIT deposit gets Income counterpart, DEBIT card gets Expenses counterpart, amounts sum to zero.)
- [x] 6. Self-transfer detection: if payee/payer name matches a configurable `self_names` list (default: names observed in sample data — the user's own full name variants), counterpart becomes `Equity:Transfers:Wise` and narration keeps the original description. (Verification: unit test — "Recebeu dinheiro de GABRIEL BARROS RODRIGUES" row books to Equity:Transfers:Wise, not Income.)

## Slice 3: Fees
- [x] 7. `FEE-CARD-*` rows → two-posting transaction (`Assets:Bank:Wise:<CURRENCY>` amount + `Expenses:BankFees:Wise` inverse), `id: wise-FEE-CARD-...`, narration "Wise Charges for: <parent id>". (Verification: unit test — FEE-CARD row balances with fee expense account.)
- [x] 8. `FEE-BALANCE-*` rows are NOT emitted standalone; they are consumed by the conversion builder (task 9). (Verification: conversion slice test — fee appears once, inside the merged conversion, and no standalone FEE-BALANCE entry exists.)

## Slice 4: Conversion merging
- [x] 9. Implement `_build_conversion(row, ...)`: triggered on `BALANCE-*` rows. For DEBIT legs, parse the destination amount+currency from Description (`\d+,\d+ <CCY> convertidos para \d+,\d+ <CCY>`), look up the matching `FEE-BALANCE-<id>` row in the same file, and emit one transaction:
  ```
  Assets:Bank:Wise:<SRC>   <net amount>
  Assets:Bank:Wise:<DST>   <dst amount> @@ <abs net amount>
  Expenses:BankFees:Wise   <fee amount>
  ```
  For CREDIT legs, return `None` (skip — same id as the DEBIT transaction). (Verification: unit test with BALANCE-5232969525 — exactly one transaction, three postings, sums to zero, fee present; run `bean-check` on a tmp file containing it → no balance error.)
- [x] 10. Wire row classification into `extract()`: classify by ID prefix (BALANCE → conversion builder, FEE-BALANCE → skip, FEE-CARD → fee builder, else → plain builder), sort entries chronologically (newest-first input), emit the balance assertion **gated by the `emit_balance` constructor flag (default False)** per amended decision [007]. (Verification: `extract()` on the SGD sample file → 206 rows in → expected entries out; header-only EUR file → `[]`; with flag off, no Balance directive appears.)

## Slice 5: Pipeline integration
- [x] 11. Register `WiseImporter` in `import.py` CONFIG. Remove the stale commented-out `Assets:Bank:Wise` pluggy account-mapping block (lines ~38–46) since Wise now has its own importer. (Verification: `python import.py identify export_samples/wise_statement_2026-01-01_2026-08-18_csv/` lists the 9 Wise files as identified; only Wise files match.)
- [x] 12. Add `include "beans/wise.bean"` to `main.bean` (create empty file). (Verification: `bean-check main.bean` passes.)

## Slice 6: End-to-end verification + real import
- [x] 13. Run the real pipeline: `python import.py extract -e beans/pluggy.bean export_samples/wise_statement_2026-01-01_2026-08-18_csv/ > tmp.wise.bean`; then `bean-check tmp.wise.bean`. All 247 transactions import; zero balance errors; conversions merged (4 conversions → 4 balanced txns); fees booked. (Verification: `bean-check` exit code 0; `rg "Assets:Bank:Wise"` shows SGD/GBP/CNY/BRL accounts; no `Income:Uncategorized:Wise` on self-transfer rows.)
- [x] 14. Spot-check in Fava: open a temporary ledger including the extracted entries and confirm holdings/net-worth pages show Wise balances and Fava's import page lists the importer. (Verification: Fava loads without errors; Wise accounts visible.)

## Slice 7: Tests + wrap-up
- [ ] 15. Write `tests/test_wise.py` mirroring `tests/test_yahoo_price_service.py` (offline, fixtures inline): header-only file, CARD row, DEPOSIT row, TRANSFER out, FEE-CARD, BALANCE DEBIT+CREDIT merge, self-transfer, sign/type mismatch warning. (Verification: `python -m pytest tests/test_wise.py -q` green.)
- [ ] 16. Update `plan/tasks.md` (mark this feature), record the sample-data facts in `docs/` if useful, and update `activeContext.md`. (Verification: files updated; activeContext reflects Wise importer as current slice.)

## Slice 8: Full-history import (resolved)
- [x] 17. User downloaded the full Wise history to `export/` (5 contiguous yearly windows, 2022-05-13 → 2026-08-18). Verified the 2022 window opens from **0** (account creation) and all windows chain: extracted all 5 with `emit_balance=True` → 1430 rows → 1352 transactions + 18 balance directives, `bean-check` exit 0. **Decision: no synthetic opening balances needed** — the full history anchors every `Assets:Bank:Wise:<CURRENCY>` account from zero (see decisions_wise.md [007] amendment). Workflow: pass each window folder to `import.py extract` in chronological order; process/accept windows in full to keep the chained balance assertions valid.