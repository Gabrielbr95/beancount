# B3 Importer Specification for Beancount

This document describes the current behavior of `importers/b3.py`.

## Scope

The importer reads two B3 XLSX report types:

1. **Negociações** — exchange-traded buys and sells
2. **Movimentações** — income, transfers, fixed income, corporate actions, and fees

The importer is intentionally strict:

- files are identified by filename only
- sheet layouts are assumed stable
- parsing errors raise exceptions
- each row decision is logged

---

## File Identification

`B3Importer.identify()` accepts only `.xlsx` files whose basename contains either:

- `movimentacao`
- `negociacao`

No inspection of file contents is used for identification.

---

## Account Model

### Root account

The importer uses the configured account root:

```text
Assets:Investment
```

The B3 account path is:

```text
Assets:Investment:B3
```

### Broker code mapping

The institution field is normalized and mapped to a broker code.

Supported mappings:

- `XP INVESTIMENTOS CCTVM S/A` → `XP`
- `XP SERVICOS FINANCEIROS DTVM LTDA` → `XP`
- `XP INVESTIMENTOS CORRETORA DE CAMBIO, TITULOS E VALORES MOBI` → `XP`
- `XP INVESTIMENTOS CORRETORA DE CAMBIO TITULOS E VALORES MOBILIARIOS S/A` → `XP`
- `MODAL DTVM LTDA` → `XP`
- `CLEAR CORRETORA - GRUPO XP` → `XP`
- `INTER DISTRIBUIDORA DE TITULOS E VALORES MOBILIARIOS LTDA` → `Inter`
- `BANCO DO BRASIL S/A` → `BB`

Broker-specific accounts are constructed as:

```text
Assets:Investment:<BROKER>:<TICKER>
Income:Investment:<BROKER>:<CATEGORY>
Expenses:Investment:<BROKER>:<CATEGORY>
```

BRL settlement legs are not posted to an investment cash account. They are
routed through broker-specific transfer accounts so the matching external cash
report can supply the other side:

```text
Equity:Transfers:XP:Rendimento
Equity:Transfers:XP:Dividend
Equity:Transfers:XP:JCP
Equity:Transfers:<BROKER>:Cash
```

`Equity:Transfers:<BROKER>:Cash` is used for trades and all other cash-settled
events. The three dedicated XP routes are used only for their corresponding
income event types.

---

## Normalization Rules

### Text normalization

The importer normalizes text by:

1. removing accents
2. converting to uppercase
3. trimming whitespace
4. collapsing repeated whitespace

### Date parsing

Dates are accepted in these formats:

- `dd/mm/YYYY`
- `dd/mm/YY`
- `YYYY-mm-dd`

### Decimal parsing

The importer accepts values such as:

- `1234,56`
- `1.234,56`
- `R$ 1.234,56`
- `1234.56`

Blank values and `-` are treated as missing.

### Ticker normalization

For exchange-traded assets, the importer uses the ticker as provided, with an additional cleanup for symbols like `PETR4F`:

- `PETR4F` becomes `PETR4`

For products without a clean ticker, the importer derives a synthetic symbol from the product name:

- remove accents
- convert to uppercase
- replace non-alphanumeric characters with `-`
- collapse repeated `-`
- if the result starts with a digit, prefix `T-`

Example outputs:

- `Tesouro Selic 2029` → `TESOURO-SELIC-2029`
- `CDB Banco ABC 2028` → `CDB-BANCO-ABC-2028`
- `10 ANOS` → `T-10-ANOS`

---

## Metadata

Every generated directive includes metadata with:

- `id`
- `source`
- `asset`

Some directives also include:

- `warning`

### Source values

- `b3_negociacoes`
- `b3_movimentacoes`

### Warning values currently emitted by the importer

- `needs_review`
- `unmatched_transfer`

The importer does **not** currently emit a generic `unknown_event_type` warning. Unknown movement types raise `ValueError`.

---

## Negociações Report

The importer reads the first non-empty row in each `NEGOCIACAO` sheet to determine the report date, then processes all non-empty rows.

### Supported trade types

#### COMPRA

Produces a purchase transaction:

- asset posting to `Assets:Investment:<BROKER>:<TICKER>`
- settlement posting to `Equity:Transfers:<BROKER>:Cash`
- optional fee posting to `Expenses:Investment:<BROKER>:Fees`

If the price is missing, it is derived from `abs(value) / abs(quantity)`.

#### VENDA

Produces a sale transaction:

- settlement posting to `Equity:Transfers:<BROKER>:Cash`
- asset posting with empty cost spec `{}`
- optional fee posting to `Expenses:Investment:<BROKER>:Fees`

If the price is missing, it is derived from `abs(value) / abs(quantity)`.

### Unsupported trade types

Any other trade type raises:

```text
ValueError(... unsupported negociacao type ...)
```

---

## Movimentações Report

The importer reads the first non-empty row in each `MOVIMENTACAO` sheet to determine the report date, then processes all non-empty rows.

### Ignored movements

These movement types are skipped entirely:

- `ATUALIZACAO`
- `DIREITO DE SUBSCRICAO`
- `DIREITOS DE SUBSCRICAO - EXERCIDO`
- `DIREITOS DE SUBSCRICAO - NAO EXERCIDO`
- `CESSAO DE DIREITOS`
- `CESSAO DE DIREITOS - SOLICITADA`
- `RECIBO DE SUBSCRICAO`
- `SOLICITACAO DE SUBSCRICAO`
- `TRANSFERENCIA - LIQUIDACAO`
- `RESGATE`
- `CISAO`
- `INCORPORACAO`
- `FRACAO EM ATIVOS`

### Income events

Supported movements:

- `RENDIMENTO`
- `DIVIDENDO`
- `DIVIDENDO - TRANSFERIDO`
- `RENDIMENTO - TRANSFERIDO`

Behavior:

- XP creates a receipt in `Equity:Transfers:XP:Rendimento` or
  `Equity:Transfers:XP:Dividend`, based on the movement type; other brokers
  use `Equity:Transfers:<BROKER>:Cash`
- books the offset to `Income:Investment:<BROKER>:Rendimento` or `Income:Investment:<BROKER>:Dividend`
- if the movement contains `TRANSFERIDO`, metadata includes `warning: "needs_review"`

### JCP

Supported movements:

- `JUROS SOBRE CAPITAL PROPRIO`
- `JUROS SOBRE CAPITAL PROPRIO - TRANSFERIDO`

Behavior:

- XP cash goes to `Equity:Transfers:XP:JCP`; other brokers use
  `Equity:Transfers:<BROKER>:Cash`
- offset goes to `Income:Investment:<BROKER>:JCP`
- transferred variants add `warning: "needs_review"`

### Interest payment

Supported movement:

- `PAGAMENTO DE JUROS`

Behavior:

- cash goes to `Equity:Transfers:<BROKER>:Cash`
- offset goes to `Income:Investment:<BROKER>:Interest`

### Corporate actions

Supported movements:

- `BONIFICACAO EM ATIVOS`
- `DESDOBRO`
- `GRUPAMENTO`

Behavior:

- the importer requires a non-zero quantity
- zero-quantity events are skipped
- the importer emits a `Custom` directive named `bonificacao`, `desdobramento`,
  or `grupamento`, with values `[ticker, 0]`
- ratio `0` is a sentinel: the event must be enriched before it can be applied

This is a placeholder implementation rather than a full accounting of the split ratio.

### Fraction auction

Supported movement:

- `LEILAO DE FRACAO`

Behavior:

- cash goes to `Equity:Transfers:<BROKER>:Cash`
- asset posting uses the quantity in the report
- if `unit_price` is missing, it is derived from `abs(value) / abs(quantity)`
- optional fee posting is created when `abs(value)` differs from gross proceeds

### Asset transfer

Supported movement:

- `TRANSFERENCIA`

Behavior:

- quantity is required
- direction is taken from the row's `direction` field
- `DEBITO` → negative quantity
- anything else → positive quantity
- the importer posts against `Equity:Transfers`
- metadata includes `warning: "unmatched_transfer"`

### Redemption

Supported movements:

- `RESGATE ANTECIPADO/`
- `RESGATE ANTECIPADO`

Behavior:

- quantity and value are required
- zero quantity is rejected
- if `unit_price` is missing, it is derived from `abs(value) / abs(quantity)`
- cash goes to `Equity:Transfers:<BROKER>:Cash`
- asset posting uses negative quantity and the computed price
- optional fee posting is created when gross proceeds differ from reported value

### Purchase / application

Supported movements:

- `COMPRA`
- `APLICACAO`

Behavior:

- quantity and value are required
- if `unit_price` is missing, it is derived from `abs(value) / abs(quantity)`
- asset posting uses the reported quantity and computed cost
- cash goes to `Equity:Transfers:<BROKER>:Cash`
- optional fee posting is created when reported value differs from gross value

### Buy/sell hybrid

Supported movements:

- `COMPRA / VENDA`
- `COMPRA/VENDA`

Behavior depends on `direction`:

- `DEBITO` → treated as a sale
- otherwise → treated as a purchase

The same quantity/value/unit price rules apply as above.

### Fees

Any movement whose normalized name contains either:

- `TAXA`
- `COBRANCA`

is treated as a fee event:

- expense goes to `Expenses:Investment:<BROKER>:Fees`
- settlement is posted to `Equity:Transfers:<BROKER>:Cash`

### Unsupported movements

Any other movement type raises:

```text
ValueError(... unsupported movement type ...)
```

---

## Transaction Ordering and Logging

- Entries are sorted by `(entry.date, lineno)` before returning.
- File-level start/finish logging is emitted.
- Individual row decisions are logged:
  - imported purchase/sale/income/etc.
  - ignored rows
  - unsupported movements before raising

---

## Current Behavioral Notes

### Notable differences from the old specification

- Transfer pairing is **not** implemented.
- `RESGATE` is ignored, not imported.
- `GRUPAMENTO` does **not** synthesize old/new lots; it currently emits a placeholder split custom directive.
- `CISÃO` and `INCORPORAÇÃO` are ignored.
- Unknown movements do **not** generate a warning directive; they raise.

### Intended manual review markers

The importer uses metadata warnings for cases that need attention later:

- `needs_review`
- `unmatched_transfer`

---

## Summary

The current importer is a strict row-to-directive mapper for B3 XLSX exports. It handles common exchange trades, income events, fixed-income operations, transfers, fees, and a limited set of corporate actions, while ignoring or rejecting unsupported movements.
