# Beancount Transaction Strategies

> Reference for agent conversations. Distilled from the official Beancount
> docs: **Command-line Accounting Cookbook** and **Trading with Beancount**
> (both by Martin Blais) plus community guidance (Lazy Beancount).
> Usage: read this file before suggesting or editing ledger entries.
>
> **Important caveat**: these are the *canonical community recommendations*,
> **not hard requirements**. The user deliberately chose NOT to follow some of
> them in this ledger. Do not treat any recommendation here as a directive to
> "fix" the ledger. When a recommendation conflicts with existing ledger
> practice, the existing practice wins unless the user asks to change it.

---

## 1. Account structure

### 1.1 Naming convention (cookbook recommendation)

`Type:Country:Institution:Account:SubAccount` for Assets, Liabilities, Income.
For Expenses, skip the institution and use a category hierarchy
(`Expenses:Food:Grocery`). If all business is in one country, the country
component may be dropped.

### 1.2 Choosing an account type

Two tests:

1. **Balance sheet vs income statement**: if the amount must persist in a
   total forever → Assets or Liabilities. If only a *period* matters
   ("how much this month?") → Income or Expenses.
2. **Sign convention**: generally positive/good → Assets or Expenses.
   Generally negative/bad → Liabilities or Income.

Examples: a meal is an Expense (transitional value only). An interest payment
is cash into an Assets account with the offset leg in `Income:...:Interest`.

### 1.3 Investment accounts

- Dedicated **Cash sub-account** for uninvested funds, e.g. `Assets:...:Cash`.
- **One sub-account per commodity** held (each stock/fund on its own line in
  the balance sheet). Not strictly necessary but recommended for reporting.
- **Income accounts mirror the institution**: `Income:...:Dividends`,
  `Income:...:PnL` (capital gains), `Income:...:Interest`. Split them —
  needed for tax declarations.
- Commissions/fees: `Expenses:Financial:Commissions` /
  `Expenses:Financial:Fees`.

### 1.4 Opening dates (cookbook recommendation)

Evergreen accounts (expense categories) may be opened at a very early
sentinel date; real accounts at their real opening date; employer income
accounts at hire date. This is a *preference*, not a rule.

---

## 2. Core transaction patterns

### 2.1 Pure transfer (bank → broker)

Both legs Assets, no Income/Expense. A transfer is *not* an expense; this is
what distinguishes savings rate from spending.

### 2.2 Currency conversion

Use the `@` price annotation, **never** `{cost}` syntax for plain currencies:

```
2014-03-03 * "Transfer from Swiss account"
  Assets:CH:UBS:Checking       -9000.00 CHF
  Assets:US:BofA:Checking      10000.00 USD @ 0.90 CHF
```

`{cost}` is for commodities that keep a cost basis. Once money is converted,
it has no cost. Beancount auto-corrects residual FX imbalance via a
conversions entry.

### 2.3 Buy

```
2014-02-16 * "Buying some LQD"
  Assets:US:ETrade:LQD                 10 LQD {119.24 USD}
  Assets:US:ETrade:Cash          -1199.35 USD
  Expenses:Financial:Commissions     6.95 USD
```

### 2.4 Sell

Reduce the specific lot by cost (`{160.00 USD}`) or cost+date; leave the P/L
posting amountless and let Beancount auto-fill it:

```
2014-02-17 * "Selling some IBM"
  Assets:US:ETrade:IBM          -3 IBM {160.00 USD} @ 170.00 USD
  Assets:US:ETrade:Cash          500.05 USD
  Expenses:Financial:Commissions   9.95 USD
  Income:US:ETrade:PnL            ;; auto-filled -30 USD
```

The `@ price` is documentation only — balancing ignores it. The P/L amount is
derived from cash received + commissions vs. cost basis of the lots sold.

### 2.5 Dividends

Cash:
```
2014-02-01 * "Cash dividends received"
  Assets:Investments:Cash            171.02 CAD
  Income:Investments:Dividends
```

Reinvested in shares: booked like a purchase, with cost basis supplied.

---

## 3. Corporate actions

### 3.1 Stock split

Official pattern — empty the position and recreate at the adjusted price
(no special syntax):

```
2004-12-21 * "Autodesk stock splits"
  Assets:US:MSSB:ADSK          -100 ADSK {66.30 USD}
  Assets:US:MSSB:ADSK           200 ADSK {33.15 USD}
```

Caveats:
- **Lot continuity is lost**: purchase dates reset, breaking holding-period /
  tax timing. Mitigation: dated lots (`{33.15 USD, 2014-01-15}`) preserve
  original acquisition dates.
- The price graph shows a discontinuity (a unit means something different
  before/after the split).

### 3.2 Cost basis adjustment / return of capital

Same empty-and-recreate pattern, plus an Income leg to absorb the basis
change:

```
2014-04-07 * "Cost basis adjustment for XSP"
  Assets:CA:RRSP:XSP           -100 ADSK {21.10 CAD}
  Assets:CA:RRSP:XSP            100 ADSK {23.40 CAD}
  Income:CA:RRSP:Gains      -230.00 CAD
```

---

## 4. Commission precision

The simple pattern (separate `Expenses:Financial:Commissions`) gives an
*approximation* of net P/L. For tax-accurate realized P/L, fold acquisition
commissions into the cost basis (e.g., $10 fee on 100 shares → `{80.10 USD}`
per share). The official docs admit there is no clean syntax for the exact
method; the simple pattern is acceptable for most personal ledgers.

---

## 5. Cash tracking

Martin Blais's personal rule (a preference, not doctrine):
- Don't track food/alcohol cash expenses.
- Keep receipts for other cash purchases and enter later.
- Periodically count the wallet and add a `balance` assertion, then book a
  lump "cash distribution" expense to balance the account.
- `pad` between assertions is legitimate for unbooked cash.

---

## 6. Workflow strategies

- **Use the trade date**, not settlement date, for trades.
- **Balance assertions** are the anti-error mechanism; they make editing
  history safe.
- **Single-legged imports**: bank/CV transactions import with one leg (the
  account), the human fills the second leg. This is the pattern behind
  smart_importer / PredictPostings in this project.
- The ledger does not need "closing a year" — reports compute any period.

---

## 7. Booking methods (lot matching — related but distinct)

Distinct from entry-writing strategy: how reductions match lots in an
inventory. Set globally (`option "booking_method" "STRICT"`) or per-account
(third string on `open`). Current v3 methods: STRICT (default),
STRICT_WITH_SIZE, NONE, AVERAGE, FIFO, LIFO, HIFO. See official doc
"How Inventories Work" for details. The v3 additions (STRICT_WITH_SIZE,
HIFO, AVERAGE) came from "A Proposal for an Improvement on Inventory
Booking."

---

## 8. Sources

- Command-line Accounting Cookbook —
  https://beancount.github.io/docs/command_line_accounting_cookbook/
- Trading with Beancount —
  https://beancount.github.io/docs/trading_with_beancount/
- How Inventories Work —
  https://beancount.github.io/docs/how_inventories_work/
- A Proposal for an Improvement on Inventory Booking —
  https://beancount.github.io/docs/a_proposal_for_an_improvement_on_inventory_booking/
- Lazy Beancount (community opinionated guide) — https://lazy-beancount.xyz/