# Specification

## Objective
Overhaul the B3 beancount pipeline so that corporate actions (splits, reverse splits,
bonus shares) are cleanly separated from transactions and income events, enriched with
reliable ratio data from Yahoo Finance, and consumed correctly by `stock_split.py`.
BRAPI is retained as a study reference and future paid-tier option.

## Core Requirements

### 1. B3 Importer (`importers/b3.py`)
- Differentiate `BONIFICACAO EM ATIVOS`, `DESDOBRO`, `GRUPAMENTO` into distinct
  `custom` directives: `"bonificacao"`, `"desdobramento"`, `"grupamento"`.
- Store raw B3 quantity in metadata (`quantity`). Emit ratio `"0"` as sentinel
  (not yet enriched). Tag with `^b3`.
- All other entry types unchanged.

### 2. Yahoo Finance Price Service (`plugins/yahoo_price_service.py`)
- Primary price and events source. Uses `yfinance`. Free, no API key.
- Appends `.SA` suffix to all tickers for Yahoo lookup.
- Maps Yahoo split `numerator/denominator` → directive type:
  - ratio > 1 and integer → `"desdobramento"`
  - ratio < 1 → `"grupamento"`
  - ratio > 1 and non-integer → `"bonificacao"`
- Emits dividends as `"dividendo"` (reference only — not used in reconcile logic).
  Yahoo does not distinguish JCP from dividendo; income reconciliation deferred.
- Tags all entries with `^yahoo`.
- Same output file format as BRAPI service (`prices/TICKER.bean`, `prices/TICKER_events.bean`).
- `_events.bean` files are reference only — NOT included in the ledger.

### 2b. BRAPI Price Service (`plugins/brapi_price_service.py`) — study reference
- Retained unchanged. Not wired to Fava extension.
- Can be run manually if BRAPI paid tier is ever activated.
- Output format is identical to Yahoo service (same directive names, same tags pattern).

### 3. Reconcile Script (`reconcile_actions.py`)
- Reads `tmp.bean` (beangulp extract output).
- Reads `prices/*_events.bean` (BRAPI reference data).
- Routes entries to three output files:
  - `transactions.bean` — buys, sells, transfers, fees, redemptions, fraction auctions.
  - `income_events.bean` — dividendo, rendimento, JCP, interest.
  - `corporate_actions.bean` — desdobramento, grupamento, bonificação.
- Enriches `corporate_actions.bean`: matches B3 entry to Yahoo event (±5 days,
  same ticker, same type — split types only: desdobramento/grupamento/bonificacao).
  Flags entries with no Yahoo match as `; ⚠ no Yahoo match — ratio unknown`.
  Flags date mismatches >1 day.
- Income sanity-check dropped — Yahoo dividend data cannot reliably distinguish
  JCP from dividendo; B3 is ground truth for income amounts.
- Default mode: append (dedup by `id` metadata). Flag `--rewrite` for full rewrite.
- Does NOT delete `tmp.bean` after run.
- Prints discrepancy report to stdout.

### 4. `stock_split.py`
- Read `"desdobramento"`, `"grupamento"`, `"bonificacao"` directives instead of
  `"split"`.
- Skip entries with ratio `"0"` and emit a loud error (ratio not yet enriched).
- All three types: multiply units × ratio, divide cost ÷ ratio. Logic otherwise
  unchanged.

### 5. File Layout
| File | Role | In ledger? |
|---|---|---|
| `transactions.bean` | Buys, sells, transfers, fees | Yes |
| `income_events.bean` | Dividendo, JCP, rendimento, interest | Yes |
| `corporate_actions.bean` | Desdobramento, grupamento, bonificação — curated | Yes |
| `prices/TICKER_events.bean` | Yahoo Finance reference data — splits, dividends | No |
| `tmp.bean` | beangulp extract output — scratch | No |

## Out of Scope
- BRAPI paid tier integration (retained as study reference in `brapi_price_service.py`).
- Bonificação cost basis correction (future — needs par value data).
- `stock_split.py` multi-split ordering bug (known, deferred).
- JCP/rendimento distinction from Yahoo dividends (Yahoo has no label field).
- Subscription rights, incorporação, cisão (remain in `IGNORED_MOVEMENTS`).
- Any changes to price fetching logic in `brapi_price_service.py`.

## User Interaction
```
# Step 1: extract from B3 exports
.venv\Scripts\python import.py extract export\ > tmp.bean

# Step 2: route, enrich, sanity-check
.venv\Scripts\python reconcile_actions.py tmp.bean

# Step 2 (full rewrite):
.venv\Scripts\python reconcile_actions.py tmp.bean --rewrite

# Step 3: update Yahoo prices and events
# (run via Fava extension as before)
```
