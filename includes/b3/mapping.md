# B3 Export Mapping Guide

This document describes how to map the Portuguese B3 export files to the Beancount ledger structure.

## 1. Negociação (Trade History)
**Source File:** `negociacao-YYYY-MM-DD.xlsx`
**Sheet:** `Negociação`

| Export Column | Beancount Mapping | Notes |
|---------------|-------------------|-------|
| `Data do Negócio` | Transaction Date | Format: `YYYY-MM-DD` |
| `Tipo de Movimentação` | Transaction Type | `Compra` (Buy) or `Venda` (Sell) |
| `Mercado` | Metadata | e.g., `Mercado à Vista`, `Mercado Fracionário` |
| `Instituição` | Account Root | e.g., `CLEAR CORRETORA` -> `Assets:Investment:Clear` |
| `Código de Negociação` | Commodity & Account | e.g., `BBAS3` -> `Assets:Investment:Clear:BBAS3` (auto-created) |
| `Quantidade` | Posting Amount | Positive for Buy, Negative for Sell |
| `Preço` | Cost/Price | Used in `{PRICE CURRENCY}` or `@ PRICE CURRENCY` syntax |
| `Valor` | Total Value | Used to balance the transaction |

**Example Trade (Compra):**
```beancount
2024-05-09 * "Compra BBAS3"
  id: "clear-txn-9834521"
  Assets:Investment:Clear:BBAS3    100 BBAS3 {27.15 BRL}
  Assets:Investment:Clear:Cash    -2855.00 BRL
  Expenses:Investment:Clear:Fees      5.00 BRL
```

## 2. Movimentação (Cash & Corporate Actions)
**Source File:** `movimentacao-YYYY-MM-DD.xlsx`
**Sheet:** `Movimentação`

| Export Column | Beancount Mapping | Notes |
|---------------|-------------------|-------|
| `Data` | Transaction Date | Format: `YYYY-MM-DD` |
| `Entrada/Saída` | Sign of Amount | `Credito` = Positive, `Debito` = Negative |
| `Movimentação` | Income/Expense Account | See mapping table below |
| `Produto` | Metadata / Commodity | e.g., `BBAS3 - BANCO DO BRASIL S/A` |
| `Instituição` | Account Root | e.g., `XP INVESTIMENTOS` -> `Assets:Investment:Clear` |
| `Valor da Operação` | Posting Amount | The BRL value of the event |

**Movement Type Mapping:**
- `Dividendo` -> `Income:Investment:<Institution>:Dividend`
- `Juros Sobre Capital Próprio` -> `Income:Investment:<Institution>:JCP`
- `Rendimento` (FIIs) -> `Income:Investment:<Institution>:Dividend` (or create `Rendimento` if preferred)
- `Atualização` -> Requires manual review (may be a non-cash corporate action, note, or inventory adjustment)

**Example Dividend:**
```beancount
2025-12-12 * "Dividendo WEGE3"
  id: "clear-div-20251212-wege3"
  Assets:Investment:Clear:Cash          273.36 BRL
  Income:Investment:Clear:Dividend     -273.36 BRL
    asset: "WEGE3"
```

**Example JCP (with withholding tax):**
```beancount
2025-12-12 * "JCP WEGE3"
  id: "clear-jcp-20251212-wege3"
  Assets:Investment:Clear:Cash           75.68 BRL   ; net (after 15% WHT)
  Expenses:Investment:Clear:Taxes        13.35 BRL
  Income:Investment:Clear:JCP           -89.03 BRL
    asset: "WEGE3"
```

## 3. Opening Balance
Use `pad` and `balance` directives to establish initial holdings.

```beancount
2024-01-01 open Assets:Investment:Clear:Cash BRL
2024-01-01 open Equity:Portfolio:Clear:Opening BRL

2024-01-01 pad  Assets:Investment:Clear:Cash Equity:Portfolio:Clear:Opening
2024-02-01 balance Assets:Investment:Clear:Cash 3200.00 BRL