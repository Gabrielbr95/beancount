# Specification — Wise (TransferWise) Importer

## Objective
Import the user's Wise per-currency balance statement CSVs into the existing beangulp → Fava → Beancount v3 pipeline, producing balanced, deduplicatable Beancount transactions.

## Background (verified facts, 2026-08-18)
- **API is not an option**: personal API tokens cannot retrieve balance statements for Brazil-based accounts (only US/CA/AU/NZ/SG/MY). Integration is CSV-file based. See `docs/Beancount - Ecosystem Research.md` §9 research and the Wise docs "Personal API tokens → Limitations".
- **Source files**: `statement_<balanceId>_<CURRENCY>_<from>_<to>.csv`, one per balance. Sample set: `export_samples/wise_statement_2026-01-01_2026-08-18_csv/` (9 files, 4 with activity: SGD 206, GBP 38, CNY 2, BRL 1; 5 header-only/empty).
- **CSV shape** (verified): rich 23-column format, comma-delimited, all fields quoted, no BOM, UTF-8, **day-first dates** (`DD-MM-YYYY`), rows **newest-first**. `Running Balance` = balance *after* that row.
- **Transaction ID prefixes** (dedup keys):
  - `TRANSFER-*` — external deposits ("Recebeu dinheiro de X") and outgoing transfers ("Enviou dinheiro para Y").
  - `CARD-*` — card purchases (DEBIT) and refunds (CREDIT rows).
  - `FEE-CARD-*` — per-card purchase fee, separate row, in the balance currency.
  - `BALANCE-*` — internal conversions between own balances: DEBIT leg in the source-currency file, CREDIT leg in the destination-currency file, **same ID in both files**. The DEBIT row's description embeds both amounts and the fee: `"300,00 GBP convertidos para 516,61 SGD (fee: 1,02 GBP)"`. The CSV debit amount is net of fee (300.00 − 1.02 = −298.98).
  - `FEE-BALANCE-*` — conversion fee row, present only in the source-currency file.
- **Self-transfers**: some `TRANSFER-*` rows are the user moving money between their own Wise balances (payee/payer = the user's own name, e.g. "Recebeu dinheiro de GABRIEL BARROS RODRIGUES"). These are NOT income/expense.

## Core Requirements
- Import each Wise statement CSV through beangulp, emitting Beancount transactions balanced to zero.
- **One account per balance currency**: `Assets:Bank:Wise:<CURRENCY>`.
- **Deterministic fee postings** to `Expenses:BankFees:Wise`.
- **Monthly card cashback** (`BALANCE_CASHBACK-*` rows, seen in BRL 2025) books deterministically to `Income:Cashback:Wise` (always a credit, no counterpart to reclassify).
- **Conversion pairs** (`BALANCE-*` DEBIT + CREDIT + optional fee) merged into a single balanced transaction; the CREDIT leg in the destination file is skipped (not double-booked).
- Every transaction carries `id: wise-<CURRENCY>-<TransferWise ID>` (dedup key, namespaced per currency because the same card txn can be split across two balance files), `source: "wise"`, `^wise` tag, and provenance metadata (merchant, exchange rate, fee, card last-4, payer/payee).
- Counterpart postings use placeholder accounts the user reclassifies: `Expenses:Uncategorized:Wise` / `Income:Uncategorized:Wise`. Self-transfers book to `Equity:Transfers:Wise` instead (never fake income/expense).
- Balance assertion emitted from the newest row's `Running Balance` (per currency per file).
- Header-only (empty) files produce zero entries and no error.
- Offline tests for parsing, dedup IDs, fee handling, conversion merging, empty files.

## Out of Scope (Crucial)
- **Wise API integration** (blocked for Brazil-based accounts; partnership-level OAuth not pursued).
- **CAMT.053/MT940/QIF parsing** — CSV is the import source; XML only cross-validates (see research).
- **smart_importer** auto-categorization (disabled project-wide; see import.py).
- **Historical backfill beyond a 365-day statement window** — older balances are unknown and stay a user-managed gap.
- **FX price fetching** — already handled by `plugins/yahoo_price_service.py` (Slice 15).
- Converting `BALANCE-*` legs across *separately downloaded* files at import time — handled via the debit leg's embedded description instead.
- Archiving/filing of downloaded CSV files into a folder tree (beangulp default behavior is fine; no custom filing mixin).

## User Interaction
- Download per-currency statements from Wise → Profile → Statements (CSV, one per balance, ≤365 days per export). Place them in a folder alongside existing downloads.
- Run the standard pipeline: `python import.py extract -e tmp.bean <folder> > new.bean` (or Fava's import page).
- Review the placeholder `Expenses:Uncategorized:Wise` / `Income:Uncategorized:Wise` postings in Fava and reclassify to real accounts; conversion and fee postings import correct as-is.
- Opening balances for pre-window Wise history are a separate, user-approved step (decision [006]).