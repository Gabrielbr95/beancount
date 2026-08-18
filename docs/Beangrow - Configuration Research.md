# Beangrow Configuration Research

**Research date:** 2026-08-18

This document records factual information about Beangrow configuration syntax,
the current Beangrow source repository, the local Fava extension, and the
current ledger account structure.

## Sources

- Beangrow repository: <https://github.com/beancount/beangrow>
- Configuration schema: <https://raw.githubusercontent.com/beancount/beangrow/master/beangrow/config.proto>
- Configuration handling: <https://raw.githubusercontent.com/beancount/beangrow/master/beangrow/config.py>
- Example configuration: <https://raw.githubusercontent.com/beancount/beangrow/master/example/config.pbtxt>
- Returns command: <https://raw.githubusercontent.com/beancount/beangrow/master/beangrow/compute_returns.py>
- Configuration inference: <https://raw.githubusercontent.com/beancount/beangrow/master/beangrow/configure.py>
- Investment extraction: <https://raw.githubusercontent.com/beancount/beangrow/master/beangrow/investments.py>
- Package metadata: <https://raw.githubusercontent.com/beancount/beangrow/master/pyproject.toml>
- PyPI package: <https://pypi.org/project/beangrow/>
- Historical Beancount returns document: <https://beancount.github.io/docs/calculating_portolio_returns/>

## Published and repository versions

- The latest Beangrow release observed on PyPI is `1.0.1`.
- The PyPI `1.0.1` release date is 2025-01-26.
- The Beangrow repository `master` commit observed during research was
  `1477a7efc49001dc5c2fa9f19fb3a426a164c0d1`, dated 2025-10-15.
- The repository contains changes after the PyPI `1.0.1` release.
- The June 2025 reinvested-dividend change is recorded in commit
  `bd1bf195648dda73c47af945a5191ec16b2ab557` and pull request #46.

## Configuration format

- The configuration file uses Protocol Buffers text format.
- The top-level configuration message contains:
  - `investments`
  - `groups`
  - repeated `benchmark_portfolio`
- An `investments` message contains repeated `investment` messages and optional
  `income_regexp` and `expenses_regexp` fields.
- An investment contains:
  - `currency`
  - `asset_account`
  - repeated `dividend_accounts`
  - repeated `match_accounts`
  - repeated `cash_accounts`
- An investment's `asset_account` is required to be an exact account name. The
  current configuration reader asserts that this field contains no glob
  characters.
- `dividend_accounts`, `match_accounts`, and `cash_accounts` may contain
  account globs.
- Group entries contain:
  - `name`
  - repeated `investment`
  - optional `currency`
  - repeated `benchmark_portfolio`
- A group investment pattern is expanded against the configured investment
  `asset_account` values.
- An account glob that matches no ledger account expands to an empty list.
- An explicit non-glob account name is retained even when it does not occur in
  the ledger.
- The glob syntax uses Python `fnmatch`, including `*` and `?`.
- Configuration comments use `#`.

### Configuration example

```protobuf
investments {
  investment {
    currency: "VUSD"
    asset_account: "Assets:Investment:IBKR:VUSD"
    dividend_accounts: "Income:Investment:IBKR:VUSD:Dividend"
    cash_accounts: "Assets:Bank:IBKR:Cash:USD"
  }
}

groups {
  group {
    name: "Broker IBKR"
    investment: "Assets:Investment:IBKR:*"
    currency: "USD"
  }
}
```

Repeated fields are written by repeating the field name. List syntax such as
`cash_accounts: ["..."]` is not used.

## Command-line tools

The current repository defines the following commands:

```text
beangrow-returns [options] ledger config output [filter_reports ...]
beangrow-prices instrument start end
beangrow-prices-file price_ledger
```

`beangrow-returns` accepts:

- `-v`, `--verbose`
- `-d`, `--days-price-threshold INTEGER`
- `-e`, `--end-date YYYY-MM-DD`
- `--pdf`, `--pdfs`
- `-j`, `--parallel`
- `-E`, `--check-explicit-flows`

The positional `filter_reports` arguments are matched against group names.

The default report output includes HTML directories. The output tree can
include:

```text
config.pbtxt
investments/
groups/
prices/
prices/prices.beancount
```

PDF output requires an external `google-chrome` executable.

The repository contains `configure.py`. It accepts a ledger and an optional
output configuration path, and has `-v/--verbose` and `-s/--start-date`
options. It is not registered as a console script in the current package
metadata.

## Package compatibility metadata

The current repository package metadata declares:

```text
requires-python = ">= 3.10"
beancount >= 2.3.6
protobuf >= 5.29.3
```

The package metadata lists Python 3.10, 3.11, 3.12, and 3.13 classifiers.

The current source imports Beancount modules including:

```python
from beancount import loader
from beancount.core import convert
from beancount.core import getters
from beancount.core import prices
from beancount.parser import printer
```

The local project uses Beancount 3.2.3. The local virtual environment contains
`fava-portfolio-returns 2.7.0`, which vendors Beangrow source under:

```text
fava_portfolio_returns/_vendor/beangrow/
```

The local project does not have standalone Beangrow package metadata or a
`beangrow-returns` executable installed.

## Configuration inference behavior

The inference script identifies balance-sheet accounts whose leaf account name
matches a declared commodity. It creates one investment configuration entry
for each matching account.

The inference script searches for dividend accounts using an account-name
pattern ending in `:Dividend` or `:Dividends`.

The inference script identifies cash accounts from accounts encountered in
matching transactions whose names end in `Cash`, `Checking`, `Receivable`, or
`GSURefund`, or contain `Receivable` or `Payable`.

When run against this ledger, the local inference script produced investment
entries for `Assets:Bank:IBKR:Cash:GBP` and
`Assets:Bank:IBKR:Cash:USD`, because `GBP` and `USD` are declared commodities
and are leaf account names. These entries were present in the generated output
alongside the security investment accounts.

## Transaction categorization

Beangrow categorizes postings using the configured account lists:

- `asset_account` → `ASSET`
- `dividend_accounts` → `DIVIDEND`
- `cash_accounts` → `CASH`
- accounts matching `income_regexp` (default prefix `Income:`) → `INCOME`
- accounts matching `expenses_regexp` (default prefix `Expenses:`) → `EXPENSES`
- remaining postings → `OTHER` or `OTHERASSET`, depending on whether a cost is
  present

Transactions are selected for an investment when they contain a posting to the
asset account, a dividend account, or a match account.

Cash-account postings are used to create cash flows after a transaction has
been selected.

The current source handles reinvested dividends by generating two flows from
the asset posting:

1. a dividend flow;
2. an equal and opposite reinvestment flow.

## Prices and currency conversion

- Return calculations use prices from the Beancount ledger.
- Beangrow records price lookups needed by report calculations.
- Generated missing-price data can be written below the report output's
  `prices` directory.
- The price download tools use `beanprice` and Yahoo Finance.
- A group containing multiple cost currencies can specify a reporting
  `currency`.
- A group without a specified currency uses its single detected cost currency;
  the local Fava extension raises an error when multiple cost currencies are
  detected and no target currency is supplied.

## Historical documentation differences

The local document `docs/Beancount - Calculating Portfolio Returns.md` dates
from September 2020 and documents the earlier
`experiments/returns/compute_returns.py` command.

The current standalone command is `beangrow-returns`.

The historical document describes reinvested dividends as producing no cash
flow. The current Beangrow source contains later reinvested-dividend handling
that exposes dividend and reinvestment flows separately.

## Local ledger observations

The current ledger has 56 investment asset accounts:

| Broker/account group | Count |
|---|---:|
| BB | 1 |
| IBKR | 6 |
| Inter | 3 |
| XP | 46 |

The current account patterns include:

```text
Assets:Investment:BB:CDB-BB
Assets:Investment:IBKR:<SYMBOL>
Assets:Investment:Inter:<SYMBOL>
Assets:Investment:XP:<SYMBOL>
```

The current ledger contains these broker cash-account patterns:

```text
Assets:Bank:BB:Cash
Assets:Bank:IBKR:Cash:USD
Equity:Transfers:BB:Cash
Equity:Transfers:Inter:Cash
Equity:Transfers:XP:Cash
Assets:Investment:XP:Cash
```

The IBKR VUSD dividend account is:

```text
Income:Investment:IBKR:VUSD:Dividend
```

The Inter interest account is:

```text
Income:Investment:Inter:Interest
```

XP distributions currently use generic accounts:

```text
Income:Investment:XP:Dividend
Income:Investment:XP:JCP
Income:Investment:XP:Rendimento
```

The corresponding transfer accounts are:

```text
Equity:Transfers:XP:Dividend
Equity:Transfers:XP:JCP
Equity:Transfers:XP:Rendimento
```

These XP distribution postings do not contain a security-specific income
account path. Security identifiers are present in transaction metadata in the
ledger imports.

## Current project configuration file

The project file `beangrow.pbtxt` contains:

- 56 exact investment entries;
- one group each for BB, IBKR, Inter, and XP;
- `BRL` as the reporting currency for BB, Inter, and XP groups;
- `USD` as the reporting currency for the IBKR group;
- the IBKR VUSD dividend account;
- the Inter interest match account;
- no XP generic dividend, JCP, or rendimento account entries.

Local validation results for this file:

```text
investments: 56
Broker BB 1 BRL
Broker IBKR 6 USD
Broker Inter 3 BRL
Broker XP 46 BRL
```

The local Fava portfolio object extracted all 56 configured investments. The
group extraction produced:

```text
Broker BB 1 investment, 37 cash flows, BRL
Broker IBKR 6 investments, 35 cash flows, USD
Broker Inter 3 investments, 4 cash flows, BRL
Broker XP 46 investments, 290 cash flows, BRL
```

`bean-check main.bean` returned exit code 0 during validation.
