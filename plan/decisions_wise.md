# Decision Log — Wise Importer

## [001] CSV files are the integration point, not the Wise API
- **Date:** 2026-08-18
- **Context:** Wise personal API tokens cannot retrieve balance statements for accounts based outside US/CA/AU/NZ/SG/MY; Brazil is not supported. API-based importers (beangulp-wise, tariochbctools, rkok/beancount-wise) require partnership OAuth, RSA-SCA signing, or are unmaintained.
- **Options Considered:** (a) Wise API via python client, (b) manual CSV export + beangulp importer, (c) CAMT.053 XML parsing, (d) third-party converters (beancount.io paste tool).
- **Decision:** Use the per-currency statement **CSV exports** + a custom beangulp importer. CAMT.053 XML kept only as a cross-validation reference (verified to contain the same transactions, minus running balance/payer name).
- **Rationale:** CSV is the only low-maintenance path that works for a Brazil-based account; verified 1:1 with the XML (247/247 transactions match). CSVs carry Running Balance, Payer Name, card last-4 — fields the XML lacks.

## [002] Account hierarchy: `Assets:Bank:Wise:<CURRENCY>`
- **Date:** 2026-08-18
- **Context:** Wise balances are multi-currency; one Beancount account is needed per balance currency.
- **Options Considered:** `Assets:Bank:Wise` (single account, multi-currency), `Assets:Bank:Wise:<CURRENCY>` (per currency), `Assets:Wise:<CURRENCY>` (research-doc style).
- **Decision:** `Assets:Bank:Wise:<CURRENCY>` (e.g. `Assets:Bank:Wise:SGD`, `Assets:Bank:Wise:GBP`).
- **Rationale:** Matches the house convention (`Assets:Bank:IBKR:Cash:{currency}`) and the pre-existing commented `Assets:Bank:Wise` placeholder in `import.py`. Keeps Wise under `Assets:Bank` where Pluggy/IBKR live. The account is auto-created by `beancount.plugins.auto_accounts` on first use.

## [003] Sign convention: CSV Amount column used as-is
- **Date:** 2026-08-18
- **Context:** The Wise CSV has a single signed `Amount` column (negative = outflow, positive = inflow). A redundant `Transaction Type` (CREDIT/DEBIT) column also exists.
- **Options Considered:** (a) use signed `Amount` directly, (b) derive sign from `Transaction Type` and ignore Amount's sign, (c) both with a consistency check.
- **Decision:** Use the signed `Amount` as the posting amount, and assert `(Amount < 0) == (Transaction Type == "DEBIT")` as a sanity check, logging a warning on mismatch.
- **Rationale:** Amount is the ground truth; the type column is a free consistency check that makes format drift loud (per "make failures loud" philosophy).

## [004] Conversions are merged into one balanced transaction from the DEBIT leg
- **Date:** 2026-08-18
- **Context:** A `BALANCE-*` conversion appears as a DEBIT in the source-currency file and a CREDIT in the destination-currency file, same ID. The DEBIT row's description embeds both amounts and the fee, e.g. `300,00 GBP convertidos para 516,61 SGD (fee: 1,02 GBP)`. The CSV DEBIT amount is net of fee (−298.98 GBP). A separate `FEE-BALANCE-*` row exists in the source file.
- **Options Considered:** (a) import both legs independently as separate unbalanced transactions, (b) skip conversions and book manually, (c) merge DEBIT + CREDIT + fee into one transaction when processing the source file, using the description to find the destination amount.
- **Decision:** When the importer hits a `BALANCE-*` DEBIT row, emit a single balanced transaction. The CSV gives net amount (−298.98) and the `FEE-BALANCE-*` row gives the fee (−1.02); **gross = net + fee = 300.00** (cross-checks the description's "300,00 GBP"). The destination amount/currency (516.61 SGD) is parsed from the description:
  ```
  2026-05-04 * "Convert GBP to SGD"
    id: "wise-BALANCE-5232969525"
    Assets:Bank:Wise:GBP      -300.00 GBP
    Assets:Bank:Wise:SGD       516.61 SGD @@ 298.98 GBP
    Expenses:BankFees:Wise       1.02 GBP
  ```
  Sums to zero: −300.00 + 298.98 + 1.02 = 0. The SGD leg is priced `@@` at the **net-of-fee** value (298.98 GBP). The CREDIT leg in the destination file is skipped (same `id` — skipping explicitly avoids emitting a bogus Income placeholder). If the FEE-BALANCE row is missing, book the GBP leg at the net amount with no fee posting (still balanced: −298.98 + 298.98 = 0). Warn on `net + fee != description gross`.
- **Rationale:** Produces exact, balanced, auditable bookkeeping for a single conversion without cross-file state. Only 4 conversions exist in the sample — the merge logic is cheap. The `@@` total-price posting keeps the transaction balanced without needing a price directive.

## [005] Fee rows map deterministically to `Expenses:BankFees:Wise`
- **Date:** 2026-08-18
- **Context:** `FEE-*` rows (both `FEE-CARD-*` and `FEE-BALANCE-*`) are unambiguous bank fees.
- **Options Considered:** (a) import as separate transactions with fee expense posting, (b) fold fee into the parent transaction as a third posting, (c) drop fee rows entirely.
- **Decision:** (a) `FEE-CARD-*` rows become their own two-posting transaction (`Assets:Bank:Wise:<CURRENCY>` + `Expenses:BankFees:Wise`). (b) `FEE-BALANCE-*` rows are folded into the conversion transaction (decision [004]) as the fee posting, never standalone.
- **Rationale:** Card fees as standalone transactions keep row-to-transaction mapping 1:1 (simple to reason about, no parent lookup state). Conversion fees must be folded because they are part of the balanced conversion equation.

## [006] Counterpart postings use placeholder accounts; self-transfers use Equity:Transfers
- **Date:** 2026-08-18
- **Context:** CARD purchases, DEPOSITs and TRANSFERs have an unknown counterpart until the user categorizes them. Some TRANSFER rows are self-transfers between the user's own Wise balances (payee/payer is the user's own name) and must not create fake income/expense.
- **Options Considered:** (a) single-leg postings left to be balanced manually, (b) two-leg with `Expenses:Uncategorized:Wise` / `Income:Uncategorized:Wise` placeholders, (c) `Expenses:TODO` placeholders like legacy Pluggy entries.
- **Decision:** Emit two-posting transactions with `Expenses:Uncategorized:Wise` (outflows) or `Income:Uncategorized:Wise` (inflows) placeholders. Self-transfers (detected via a configurable list of the user's own names, defaulting to the names seen in sample data) use `Equity:Transfers:Wise` as the counterpart.
- **Rationale:** Two-posting entries always balance, so `bean-check` stays clean during review. The placeholder names are descriptive in Fava's tree. Smart importer is disabled project-wide, so placeholders are the pragmatic house pattern (matching how Pluggy entries were handled before PredictPostings was disabled).

## [007] Balance assertion: newest Running Balance, dated +1 day
- **Date:** 2026-08-18 (amended 2026-08-18)
- **Context:** Rows are newest-first; `Running Balance` is the balance *after* that row. Beancount `balance` directives assert the balance at the start of the date. Wise accounts have no ledger history until the full history is imported, so a `balance` directive against `Assets:Bank:Wise:*` would fail `bean-check` prematurely.
- **Options Considered:** (a) emit assertion unconditionally, (b) no assertion, (c) emit only when the ledger has an anchoring opening balance.
- **Decision:** Emit one `balance` directive per imported file (amount = Running Balance of the newest row, date = newest row date + 1 day) **behind a constructor flag `emit_balance` (default False)**. **Task 17 resolved:** the user downloaded the full history (2022-05-13 → 2026-08-18, 5 contiguous windows). The 2022 window starts from an opening balance of **0** (account creation), so **no synthetic opening balances are needed** — the full history itself is the anchor. `import.py` now passes `emit_balance=True`. Verified: all 5 windows extracted together with assertions enabled → `bean-check` exits 0 (1430 rows → 1352 transactions + 18 balance directives, 0 errors).
- **Rationale:** The assertion catches dropped rows at the file boundary. With the full history chaining from zero, it is meaningful for every window. Windows must be processed in chronological order and accepted in full — an out-of-order or partial acceptance fails `bean-check` loudly, which is the intended safety behavior.

## [008] Identifier: match on the Wise filename pattern
- **Date:** 2026-08-18
- **Context:** Wise exports are named `statement_<balanceId>_<CURRENCY>_<from>_<to>.csv` where balanceId is numeric and dates are ISO `YYYY-MM-DD`.
- **Options Considered:** (a) regex on filename, (b) content sniffing.
- **Decision:** `identify()` returns True when the basename matches `^statement_\d+_[A-Z]{3}_\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}\.csv$` and the currency is parseable.
- **Rationale:** Simple, no false positives on the user's other CSVs. The `<from>_<to>` window can optionally be used to emit a metadata note.

## [009] Base class: custom `beangulp.Importer` subclass, not csvbase
- **Date:** 2026-08-18
- **Context:** csvbase.Importer covers the plain "one row → one transaction" case well, but Wise needs: sign/type consistency check, self-transfer detection, conversion merging across rows, fee folding, per-currency account selection from the filename, and newest-first ordering (csvbase handles descending order, but the balance-assertion and merge logic is custom).
- **Options Considered:** (a) csvbase.Importer with overridden `extract()`/`finalize()`, (b) plain `beangulp.Importer` subclass reading the CSV with the stdlib `csv` module, (c) deprecated `csv.CSVImporter` (Evernight style).
- **Decision:** (b) plain `beangulp.Importer` subclass using stdlib `csv.DictReader` (explicit header mapping), following the house style of `importers/pluggy.py`.
- **Rationale:** Matches the existing Pluggy importer pattern the user already understands; avoids csvbase's Column-parser indirection for logic that is mostly row-classification anyway. csvbase's convenience buys little here and its `extract()` flow fights the conversion merge.

## [010] Cashback rows map deterministically to `Income:Cashback:Wise`
- **Date:** 2026-08-18
- **Context:** Full-history review surfaced `BALANCE_CASHBACK-*` rows (7 in BRL, monthly Feb–Aug 2025, description "Cashback", details type UNKNOWN). They are always CREDITs with no payer/payee — unambiguous income with no counterpart to reclassify.
- **Options Considered:** (a) let them fall through to the `Income:Uncategorized:Wise` placeholder, (b) dedicated `Income:Cashback:Wise` account.
- **Decision:** (b) dedicated account, via a small `_build_cashback_txn` builder (id/source metadata, two postings). Non-credit cashback rows warn and are skipped.
- **Rationale:** Mirrors decision [005] (fees get a dedicated expense account). Cashback needs no user reclassification, so burying it in the placeholder would create needless review work and pollute the uncategorized bucket.