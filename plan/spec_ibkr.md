# Specification

## Objective
Integrate Interactive Brokers (IBKR) into the existing Beancount ledger using the
`uabean` IBKR importer (decision [013]). The importer consumes IBKR Flex Query XML
files and produces complete Beancount transactions (trades with cost basis,
dividends, withholding tax, interest, fees, corporate actions, cash balances).

## Core Requirements

### 1. Importer (vendored uabean IBKR importer)
- **Vendored** from uabean (decision [005]): copy `src/uabean/importers/ibkr.py`
  into the project's existing `importers/` dir as `importers/ibkr.py`, plus the
  small `IdentifyMixin` it imports (`src/uabean/importers/mixins.py`), keeping
  the MIT attribution header. No `uabean` package installed.
- Only new venv dependency: **`ibflex`** (core parser + enums). Everything else
  the module imports (`beangulp` + its identifier mixin, `beancount`) is already
  installed.
- Configured with account names consistent with the existing ledger conventions
  (see Section 5).
- `identify()` must match exported Flex XML files (mime `application/xml`,
  content `<FlexQueryResponse `).
- Regression note: vendored code should be re-synced manually from upstream if
  uabean ever fixes a bug we care about (MIT, keep attribution).

### 2. Flex Query XML input
- The user creates ONE Activity Flex Query in IBKR Client Portal containing all
  required sections (from the importer module docstring):
  - **Trades** — Options: Executions, Closed Lots
  - **Cash Transactions** — Options: Dividends, Payment in Lieu of Dividends,
    Withholding Tax, 871(m) Withholding, Advisor Fees, Other Fees,
    Deposits/Withdrawals, Carbon Credits, Bill Pay, Broker Interest Paid,
    Broker Interest Received, Broker Fees, Bond Interest Paid,
    Bond Interest Received, Price Adjustments, Commission Adjustments, Detail
  - **Cash Report** — Options: Currency Breakout
  - **Corporate Actions** — Options: Detail
- First run: full history. Subsequent runs: incremental window (the ledger's
  existing entries + `use_existing_holdings=True` handle lot matching).
- Export mode: **manual download from Client Portal** (offline, fits corporate
  Windows constraints). Automated Flex Web Service download is out of scope for
  v1 (see Out of Scope).

### 3. Extraction workflow
- The vendored IBKR importer is registered in `import.py` CONFIG (decision [006],
  supersedes the earlier dedicated `import_ibkr.py` plan). This is required so
  Fava's import UI recognizes IBKR XML (`import-config` points at `import.py`).
- Entries flow through `tmp.bean` like the B3/Pluggy importers — no separate
  `beans/ibkr.bean`, no additional `main.bean` include.
- `reconcile_actions.py` is not disturbed: IBKR transactions are complete
  two-leg transactions with their own metadata (id/isin/ib_cost), not single-leg
  TODO-counterpart entries needing routing.

### 4. Output expectations from the importer
- Trades: full two-leg transactions with explicit cost lots (from Closed Lots),
  `ib_cost` metadata, fee posting flagged `C`.
- Dividends and withholding tax merged into one transaction.
- Interest, fees as two-leg transactions.
- Corporate actions (forward split, merger, issue change).
- **Deposits/withdrawals are single-leg** (payee "self") — the user must add the
  counterpart posting manually after each import (mirrors the existing Pluggy
  manual-completion pattern).
- Balance directives per currency from the Cash Report (assert IBKR cash).
- `Open` directives via `autoopen_accounts` (harmless alongside the existing
  `auto_accounts` plugin).

### 5. Account naming (consistent with existing conventions)
Configure the importer with:
- `cash_account` = `Assets:Bank:IBKR:Cash:{currency}`
- `assets_account` = `Assets:Investment:IBKR:{symbol}`
- `div_account` = `Income:Investment:IBKR:{symbol}:Dividend`
- `interest_account` = `Income:Investment:IBKR:Interest`
- `wht_account` = `Expenses:Investment:IBKR:WithholdingTax`
- `fees_account` = `Expenses:Investment:IBKR:Fees`
- `pnl_account` = `Income:Investment:IBKR:{symbol}:PnL`
- `document_archiving_account` = `ibkr`

Commodity directives for held IBKR symbols (e.g. AAPL, VTI) added to
`beans/commodities.bean` after the first import, matching the existing B3-ticker
declaration convention.

### 6. Verification
- `bean-check main.bean` exits 0 after each import (single-leg deposits are the
  only expected manual completions).
- Cost basis of held positions matches the IBKR Flex report cost basis.
- `uabean` install does not change `beangulp` behavior for the existing B3/Pluggy
  importers (regression check: `import.py extract` still works).

## Out of Scope
- **Automated Flex Web Service download** (token/queryId script) — v1 uses manual
  XML export; can be added later via `ibflex`'s client.
- **Wise integration** — future; uabean already ships a Wise importer +
  `uabean-wise-downloader`.
- **Binance integration** — future; uabean already ships a Binance importer
  (spot/P2P/savings accounts configurable).
- **Wash sale handling** — IBKR reports them; no automation (manual if needed).
- **Short positions** — supported by uabean but user does not currently short.
- **Mergers/issue-change corporate actions beyond the importer's built-in
  handling** — any structure the importer raises on will be handled manually
  on first import.
- **Changes to `import.py` / `reconcile_actions.py`** (B3/Pluggy pipeline).

## User Interaction
```bash
# Recurring workflow (e.g. monthly):
# 1. Export Flex Query XML from IBKR Client Portal → save to export/
# 2. Import via CLI (or Fava's import UI — the importer is registered in import.py)
.venv/bin/python import.py extract export/ > tmp.bean
# 3. Complete single-leg deposit/withdrawal counterparts in tmp.bean
# 4. Verify
.venv/bin/bean-check main.bean
```