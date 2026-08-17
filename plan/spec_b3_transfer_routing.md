# Specification

## Objective
Make B3 imports route every BRL settlement through a broker- and transaction-type-specific `Equity:Transfers` account, rather than through `Assets:Investment:<broker>:Cash`.

## Core Requirements
- Route XP income events by B3 movement type:
  - `RENDIMENTO` and `RENDIMENTO - TRANSFERIDO` → `Equity:Transfers:XP:Rendimento`.
  - `DIVIDENDO` and `DIVIDENDO - TRANSFERIDO` → `Equity:Transfers:XP:Dividend`.
  - `JUROS SOBRE CAPITAL PROPRIO` and its transferred variant → `Equity:Transfers:XP:JCP`.
- Route cash-settled trades and other non-income B3 events to `Equity:Transfers:<broker>:Cash`:
  - Negociações buys and sells.
  - `PAGAMENTO DE JUROS`, fraction auctions, redemptions, purchases/applications, buy/sell hybrids, and fees.
- Apply the generic cash route to every supported broker, including `XP` and `Inter`.
- Keep asset custody transfers (`TRANSFERENCIA`) unchanged: they remain commodity postings against `Equity:Transfers` and are still eligible for the existing custody-transfer merge logic.
- Keep the existing asset, income, fee, amount, cost, price, metadata, warning, and narration behaviour unchanged apart from the settlement-account route.
- Replace the ambiguous shared cash-account helper with an explicit transfer-account helper so future event types must choose a route deliberately.
- Correct `context/b3_importer.md` so its documented account paths match the code and the new routing behaviour.

## Out of Scope (Crucial)
- Rewriting existing ledger entries or migrating historical `Equity:Transfers:Investments` postings.
- Creating separate transfer routes for `Interest` or fees; both use `Equity:Transfers:<broker>:Cash`.
- Changing Pluggy imports, `scripts/reconcile_transfers.py`, or the existing `TRANSFERENCIA` custody-pairing logic.
- Adding a new external dependency or a configurable routing framework.

## User Interaction
Run the existing local B3 import command as usual. New B3 XLSX exports will contain `Equity:Transfers:<broker>:<route>` settlement postings automatically:

```text
.venv\Scripts\python import.py extract export\ > tmp.bean
```
