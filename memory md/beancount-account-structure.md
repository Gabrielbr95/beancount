# Beancount Account Structure — Personal Investment Portfolio

## Pattern

```
<AccountType> : <Intermediate> : <Institution> : <Final>
```

The intermediate classifies the **category** within each account type. The final classifies the **specific item** within that institution. This pattern is applied uniformly across all five account types.

---

## Full Account Hierarchy

### Assets — `Assets:Investment:<Institution>:<Final>`

Cash and savings accounts are pre-declared. Security and crypto accounts are auto-created per ticker by the plugin — no manual `open` directives needed for those.

```beancount
; Banco do Brasil
Assets:Investment:BB:Cash            ; conta corrente (BRL)
Assets:Investment:BB:Savings         ; poupança (BRL)
Assets:Investment:BB:PETR4           ; ← auto-created per ticker
Assets:Investment:BB:BOVA11

; Banco Inter
Assets:Investment:Inter:Cash
Assets:Investment:Inter:BOVA11       ; ← auto-created per ticker

; Clear
Assets:Investment:Clear:Cash
Assets:Investment:Clear:PETR4        ; ← auto-created per ticker
Assets:Investment:Clear:MGLU3

; Interactive Brokers
Assets:Investment:IBKR:Cash          ; USD (and any other foreign currency)
Assets:Investment:IBKR:AAPL          ; ← auto-created per ticker
Assets:Investment:IBKR:VTI

; Binance
Assets:Investment:Binance:Cash       ; USDT / BRL / stablecoins
Assets:Investment:Binance:BTC        ; ← auto-created per asset
Assets:Investment:Binance:ETH
```

---

### Liabilities — `Liabilities:Credit:<Institution>:<Final>`

```beancount
Liabilities:Credit:BB:Card
```

---

### Income — `Income:Investment:<Institution>:<Final>`

Pre-declared. All institutions may generate any income type; only declare what applies.

```beancount
; Banco do Brasil
Income:Investment:BB:Dividend        ; dividendos (isentos PF)
Income:Investment:BB:JCP             ; juros sobre capital próprio (15% WHT)
Income:Investment:BB:Interest        ; poupança, CDB, LCI, LCA, Tesouro
Income:Investment:BB:Gains           ; ganho de capital

; Banco Inter
Income:Investment:Inter:Dividend
Income:Investment:Inter:JCP
Income:Investment:Inter:Interest
Income:Investment:Inter:Gains

; Clear
Income:Investment:Clear:Dividend
Income:Investment:Clear:JCP
Income:Investment:Clear:Interest     ; renda fixa via Clear (if any)
Income:Investment:Clear:Gains

; Interactive Brokers
Income:Investment:IBKR:Dividend      ; USD dividends
Income:Investment:IBKR:Interest      ; interest on cash balance
Income:Investment:IBKR:Gains

; Binance
Income:Investment:Binance:Interest   ; Earn, savings, lending products
Income:Investment:Binance:Gains
Income:Investment:Binance:Rewards    ; staking, airdrops, referrals
```

---

### Expenses — `Expenses:Investment:<Institution>:<Final>`

```beancount
; Per-institution fees and withholding taxes
Expenses:Investment:BB:Fees
Expenses:Investment:BB:Taxes         ; IOF, IR retido na fonte

Expenses:Investment:Inter:Fees
Expenses:Investment:Inter:Taxes

Expenses:Investment:Clear:Fees
Expenses:Investment:Clear:Taxes

Expenses:Investment:IBKR:Fees
Expenses:Investment:IBKR:Taxes

Expenses:Investment:Binance:Fees
Expenses:Investment:Binance:Taxes
```

When you add living expense tracking, the institution becomes the card or bank used:

```beancount
Expenses:Living:BB:Supermarket
Expenses:Living:BB:Rent
Expenses:Living:Inter:Transport
; etc.
```

---

### Equity — `Equity:Portfolio:<Institution>:<Final>`

```beancount
Equity:Portfolio:BB:Opening
Equity:Portfolio:Inter:Opening
Equity:Portfolio:Clear:Opening
Equity:Portfolio:IBKR:Opening
Equity:Portfolio:Binance:Opening
Equity:Portfolio:Global:Opening      ; for adjustments not tied to one institution
```

---

## Summary Table

| Account type | Intermediate | Institution | Final |
|---|---|---|---|
| `Assets` | `Investment` | `BB`, `Inter`, `Clear`, `IBKR`, `Binance` | `Cash`, `Savings`, `TICKER` |
| `Liabilities` | `Credit` | `BB` | `Card` |
| `Income` | `Investment` | same | `Dividend`, `JCP`, `Interest`, `Gains`, `Rewards` |
| `Expenses` | `Investment` / `Living` | same + `Global` | `Fees`, `Taxes`, `Supermarket`, … |
| `Equity` | `Portfolio` | same + `Global` | `Opening` |

---

## Transaction Examples

### Buy (ticker account auto-created by plugin)

```beancount
2024-01-15 * "Buy PETR4"
  id: "clear-txn-9834521"
  Assets:Investment:Clear:PETR4    100 PETR4 {28.50 BRL}
  Assets:Investment:Clear:Cash    -2855.00 BRL
  Expenses:Investment:Clear:Fees      5.00 BRL
```

### Sell (gain booked automatically)

```beancount
2024-06-01 * "Sell PETR4"
  id: "clear-txn-9841002"
  Assets:Investment:Clear:PETR4   -100 PETR4 {} @ 32.00 BRL
  Assets:Investment:Clear:Cash     3195.00 BRL
  Expenses:Investment:Clear:Fees      5.00 BRL
  Income:Investment:Clear:Gains
```

### Dividend

```beancount
2024-03-20 * "Dividends PETR4 Mar/2024"
  id: "clear-div-20240320-petr4"
  Assets:Investment:Clear:Cash          85.00 BRL
  Income:Investment:Clear:Dividend     -85.00 BRL
    asset: "PETR4"
```

### JCP (with withholding tax)

```beancount
2024-03-20 * "JCP PETR4 Mar/2024"
  id: "clear-jcp-20240320-petr4"
  Assets:Investment:Clear:Cash          72.25 BRL   ; net (after 15% WHT)
  Expenses:Investment:Clear:Taxes       12.75 BRL
  Income:Investment:Clear:JCP          -85.00 BRL
    asset: "PETR4"
```

### IBKR USD dividend

```beancount
2024-04-12 * "Dividend AAPL Q1/2024"
  id: "ibkr-div-20240412-aapl"
  Assets:Investment:IBKR:Cash          8.50 USD
  Income:Investment:IBKR:Dividend     -8.50 USD
    asset: "AAPL"
```

### Binance staking reward

```beancount
2024-04-01 * "ETH Staking Mar/2024"
  id: "binance-stake-20240401-eth"
  Assets:Investment:Binance:ETH       0.005 ETH {} @ 18500.00 BRL
  Income:Investment:Binance:Rewards     -92.50 BRL
    asset: "ETH"
```

### Opening balance (pad + balance)

```beancount
2024-01-01 open Assets:Investment:Clear:Cash BRL
2024-01-01 open Equity:Portfolio:Clear:Opening BRL

2024-01-01 pad  Assets:Investment:Clear:Cash Equity:Portfolio:Clear:Opening
2024-02-01 balance Assets:Investment:Clear:Cash 3200.00 BRL
```

---

## File Organization

```
ledger/
├── main.beancount
├── commodities.beancount
├── prices.beancount
├── bank-bb.beancount
├── bank-inter.beancount
├── broker-clear.beancount
├── broker-ibkr.beancount
└── exchange-binance.beancount
```

```beancount
; main.beancount
option "operating_currency" "BRL"
option "booking_method" "AVERAGE"   ; custo médio — override per account for IBKR if needed

plugin "beancount.plugins.auto_accounts"   ; or your custom plugin

include "commodities.beancount"
include "prices.beancount"
include "bank-bb.beancount"
include "bank-inter.beancount"
include "broker-clear.beancount"
include "broker-ibkr.beancount"
include "exchange-binance.beancount"
```
