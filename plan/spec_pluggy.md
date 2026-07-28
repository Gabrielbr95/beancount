# Specification

## Objective
Build a beangulp importer that fetches bank account transactions from the Pluggy
API (via the Meu Pluggy proxy) and converts them to Beancount entries. The
importer behaves like a standard beancount importer — works with `import.py
extract` and Fava's import UI.

## Core Requirements

### 1. PluggyImporter (`importers/pluggy.py`)
- Subclass of `beangulp.Importer` (same pattern as `importers/b3.py`).
- `identify()` — recognizes a trigger file (empty file with `.pluggy` extension).
- `extract()` — authenticates with Pluggy API, fetches all accounts and
  transactions for configured item IDs, maps to Beancount entries.
- `account()` — returns root account (e.g., `Assets:Bank`).
- `date()` — returns the date of the most recent transaction fetched.
- `filename()` — returns a descriptive output filename.
- `name` property — returns `"Pluggy Importer"`.

### 2. Pluggy API Client (within `importers/pluggy.py`)
- `authenticate()` — reads credentials from `api_keys.txt`, `POST /auth`,
  returns API key. Fails loudly on auth error.
- `fetch_accounts(item_id)` — `GET /accounts?itemId=`, returns list of accounts.
- `fetch_transactions(account_id)` — `GET /v2/transactions?accountId=`, follows
  cursor pagination until exhausted. Returns list of all transactions.
- Uses `requests` library (already available). Added to `requirements.txt`.

### 3. Account Mapping
- Config dict passed via `import.py` CONFIG (same pattern as B3Importer's
  `account_root` parameter).
- Maps `{pluggy_account_id: beancount_account}` for each account.
- Bank accounts (CHECKING, SAVINGS) → `Assets:...` accounts.
- Credit card accounts (CREDIT_CARD) → `Liabilities:...` accounts.
- Accounts not in the mapping are skipped with a loud warning.

### 4. Transaction Mapping
- Each Pluggy transaction → one Beancount `data.Transaction`.
- **Single posting only**: the mapped Beancount account, with the Pluggy
  `amount` (signed).
  - CREDIT (positive) → increases bank account / increases credit card liability.
  - DEBIT (negative) → decreases bank account / decreases credit card liability.
  - The counterpart posting is NOT emitted here — it is predicted by
    `smart_importer`'s `PredictPostings` hook (see Decision [018], which
    supersedes the original two-leg TODO pattern from Decision [014]).
- **Metadata**: `id` (pluggy txn ID for dedup), `source: "pluggy"`,
  `pluggy_category`, `pluggy_merchant` (if present) — retained as provenance;
  the default `PredictPostings` hook does not consume custom metadata.
- **Narration**: Pluggy `description` (cleaned).
- **Payee**: Pluggy `merchant.name` (if present).
- **Date**: date part of Pluggy `date` field (ISO string, take first 10 chars).
- Only `POSTED` transactions are imported. `PENDING` skipped.

### 5. Credential Management
- Credentials (`clientId`, `clientSecret`) and item IDs read from `api_keys.txt`
  (gitignored, existing pattern).
- API key has ~2-hour JWT lifetime — authenticate on each run, do not cache.
- Item IDs added to `api_keys.txt` as `pluggy_item_ids = id1,id2,id3`.

### 6. Integration
- `PluggyImporter` added to `CONFIG` in `import.py`.
- Account mapping defined in `import.py` CONFIG.
- Missing Beancount accounts opened in `beans/accounts.bean` (or auto-opened by
  the `auto_accounts` plugin already active in `main.bean`).

## Out of Scope
- **smart_importer integration** — DONE (Decision [018]). Pluggy emits
  single-leg postings; `PredictPostings().hook` predicts the counterpart
  from narration/payee/day-of-month. Existing `tmp.bean` Pluggy entries
  must be manually reclassified away from `Expenses:TODO`/`Income:TODO`
  before auto-categorization is trustworthy.
- **Installment tracking** for credit card transactions (`creditCardMetadata`).
  All credit card txns treated as single postings.
- **Automatic expense categorization** — Pluggy `category` field stored in
  metadata but not mapped to Beancount accounts.
- **Webhook-based sync** — manual trigger only (user creates trigger file).
- **Balance assertions** — Pluggy provides balances; could emit Balance
  directives later.
- **Investment account transactions** — Pluggy may return investment data, but
  the B3 importer already handles B3/investment flows. Pluggy importer focuses
  on bank/credit card accounts only.
- **Incremental sync** — all transactions fetched on each run. beangulp dedup
  handles duplicates. Date filtering can be added if transaction volume grows.

## User Interaction
```bash
# Step 1: create trigger file in the import directory
touch export/pluggy.trigger

# Step 2: extract (same as B3 importer)
python import.py extract export/ > tmp.bean

# In Fava: upload a file named *.pluggy to trigger the importer
```
