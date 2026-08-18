# Beancount Ecosystem Research

> Reference for agent conversations. Research date: **2026-08-15** (live data from PyPI/GitHub). Updated **2026-08-17** with investment-portfolio & rebalancing research (§9–§10).
> Usage: read this file first to load context on the ecosystem before planning or coding.
> Key takeaway: target **Beancount v3** — Fava dropped v2 support in 1.30.13.

---

## 1. Quick Reference (front-load this)

| Project | Latest release | Date | License | Status |
|---|---|---|---|---|
| beancount | 3.2.3 | May 5, 2026 | GPL-2.0 | Active |
| fava | 1.30.14 | Jun 16, 2026 | MIT | Very active |
| beangulp | 0.2.0 (master 0.3.0.dev0) | Jan 20, 2025 | GPL-2.0 | Maintained, slow releases |
| smart_importer | 1.2 | Oct 17, 2025 | MIT | Active (beta) |
| beanquery (companion) | 0.2.0 | Mar 24, 2025 | GPL-2.0 | Active |

### Investment / portfolio tools (v3-era, 2026-08)

| Project | Latest release | Date | License | Status |
|---|---|---|---|---|
| beanprice | 2.1.0 | Oct 18, 2025 | GPL-2.0 | Active (official) |
| beangrow | — (git) | low activity | GPL-2.0 | Official, v3 OK |
| fava-investor | 1.0.1 | Jan 19, 2025 | GPL-3.0 | v2+v3 compatible |
| fava-portfolio-returns | — (git/PyPI) | active | GPL-2.0 | v3 confirmed |
| beancount_portfolio_allocation | 1.0.0 | Nov 29, 2025 | GPL-2.0 | Explicit v3 (`beancount>=3`) |

### Dependency relationships

```
beancount (core language/library)
  ├── beanquery   (SQL-like BQL engine; split out of v3 core)
  ├── beangulp    (import framework; needs beancount >=2.3.5)
  │     └── smart_importer (beangulp hooks; needs beancount>=3 + beangulp + scikit-learn)
  └── fava        (web UI; needs beancount>=3.2.0,<4 + beangulp>=0.2 + beanquery)
```

- beangulp emits `beancount.core.data` objects → depends on beancount.
- smart_importer consumes beangulp's `existing_entries` argument; registered via `HOOKS` or importer wrapping. No longer uses v2 `beancount.ingest`.
- Fava's import page drives beangulp importers; query page runs beanquery.

### Runtime / Python requirements

- beancount: Python >=3.9. Deps: ply, lxml, python-dateutil, regex, beautifulsoup4, click.
- fava: Python >=3.10. Flask-based, Svelte 5 frontend, d3.js charts.
- beangulp: Python >=3.7. Deps: beancount>=2.3.5, beautifulsoup4, chardet, click>8.0, deprecation, lxml, python-magic (non-Windows); optional petl.
- smart_importer: Python >=3.10. Deps: beancount>=3, beangulp, scikit-learn>=1.0, numpy>=1.18.0.

---

## 2. Beancount (core)

**What it is**: Double-entry bookkeeping from plain-text ledger files. The `.beancount` file format IS the standard — no external standards body, defined by the project itself. Language and library are tightly coupled (the package is both parser/validator and the API).

**Core features**:
- Directives: `open`, `close`, `commodity`, `price`, `balance` (assertions), `note`, `document`, `event`, `query`, `plugin`, `option`, `txn`.
- Transactions with postings, flags, tags, links, metadata.
- Strict balance validation; inventory with cost basis, lots, price conversion.
- Plugin system for scripting (e.g., auto-inserting postings).
- BQL query language — in v3 this lives in the separate **beanquery** package.

**CLI tools in v3** (what's still in core): `bean-check`, `bean-doctor`, `bean-example`, `bean-format`, `treeify`.
**Removed/deprecated in v3**: `bean-report`, `bean-web`, `bean-bake`. `bean-query`/`bean-extract`/`bean-identify` moved to separate packages (beanquery / beangulp patterns).

**Example ledger entry**:
```
2016-03-18 * "Whole Foods" "Weekly groceries"
  Expenses:Food:Grocery       42.30 USD
  Liabilities:CreditCard     -42.30 USD
```

**Validate**: `bean-check file.beancount`
**Query**: `bean-query file.beancount "SELECT date, narration, amount WHERE account ~ 'Expenses'"`

### Programmatic parsing: loader vs. parser

- Use `beancount.loader.load_file()` to load and validate a ledger, including
  its includes and configured plugins.
- For a fresh, direct parse of a single file—for example, comparing
  transactions by `id:` after editing a standalone extract—use:
  ```python
  from beancount.parser import parser

  entries, errors, options = parser.parse_file("file.bean")
  ```
- Project lesson: `loader.load_file()` returned stale cached results during an
  ad-hoc comparison of recently edited standalone files. Do not use it as the
  sole source for that kind of comparison without confirming it reflects the
  current file contents.
- The parser returns parser-level objects such as `CostSpec`; the loader may
  return transformed/loaded entries. Do not mix the two representations in one
  comparison.

**Key URLs**: [github.com/beancount/beancount](https://github.com/beancount/beancount) · [pypi.org/project/beancount](https://pypi.org/project/beancount) · [beancount.github.io/docs](https://beancount.github.io/docs/)

---

## 3. Fava (web UI)

**What it is**: Local web interface for Beancount ledgers. Text files stay the source of truth; Fava visualizes/reports over them.

**Usage**: `pip3 install fava && fava ledger.beancount` → serves http://localhost:5000

**Core features**:
- Reports: journal, balance sheet, income statement, trial balance, holdings/net worth, statistics, commodity/prices, documents, events.
- d3.js charts: line, area, stacked bar, treemap, sunburst.
- Query page (BQL via beanquery), table + chart results, CSV/XLS/XLSX/ODS export.
- Account tree drill-down, filters (time/account/tag/payee), currency conversion, market-value views.
- Built-in source editor (CodeMirror), transaction entry forms.
- **Import page** integrated with beangulp importers (identify/extract/archive, duplicate detection).
- Extensions, i18n, budgets, dark mode.

**Compatibility warning**: Fava 1.30.13+ **drops Beancount v2 support**. Requires `beancount>=3.2.0,<4`.

**Key URLs**: [github.com/beancount/fava](https://github.com/beancount/fava) · [pypi.org/project/fava](https://pypi.org/project/fava) · [beancount.github.io/fava](https://beancount.github.io/fava/) · [changelog](https://beancount.github.io/fava/changelog.html)

---

## 4. Beangulp (import framework)

**What it is**: Official import framework; the v3 evolution/replacement of `beancount.ingest` (v2).

**Core concepts**:
- `beangulp.Importer` subclass implements `identify()`, `account()`, `extract()` (returns Beancount directives); optional `date()`, `filename()`, `sort()`, `deduplicate()`.
- Ready-made declarative **CSV importer**: `beangulp.importers.csvbase.Importer` with column mapping, date/number parsing, credit/debit split, ordering detection, auto-balance assertions.
- `beangulp.Ingest(importers, hooks)` script pattern: subcommands `identify`, `extract`, `archive`; `--dry-run`.
- **Hook functions** apply to all imported entries — this is the plug-in point for smart_importer.
- Document filing/archiving into account-based folder tree.

**Usage pattern** (`import.py`):
```python
import beangulp
from beangulp.importers import csvbase

class MyCSVImporter(csvbase.Importer):
    date = csvbase.Date("Date", "%Y-%m-%d")
    narration = csvbase.Column("Purpose")
    amount = csvbase.Amount("Amount", subs={r",": "."})
    def identify(self, filepath): return filepath.endswith("mybank.csv")

CONFIG = [MyCSVImporter(account="Assets:MyBank", currency="EUR")]
HOOKS = []
if __name__ == "__main__":
    beangulp.Ingest(CONFIG, HOOKS)()
```

Run: `python import.py extract -e existing.beancount ./downloads > new.beancount` (the `-e`/`existing_entries` is what smart_importer trains on).

**Key URLs**: [github.com/beancount/beangulp](https://github.com/beancount/beangulp) · [pypi.org/project/beangulp](https://pypi.org/project/beangulp) · [import docs](https://beancount.github.io/docs/importing_external_data/)

---

## 5. Smart Importer (ML augmentation)

**What it is**: Predicts missing postings (accounts) and payees for single-legged imported transactions, trained on the user's existing ledger. Runs **100% locally** (scikit-learn SVC) — nothing leaves the machine.

**Core features**:
- `PredictPostings` — predicts missing postings/accounts.
- `PredictPayees` — predicts payee.
- Two integration modes: beangulp hook (`HOOKS = [PredictPostings().hook, ...]`) or importer wrapper (`PredictPostings().wrap(PredictPayees().wrap(MyBankImporter(...)))`).
- Training data = `existing_entries` from ledger (Fava passes it automatically).
- Pluggable tokenizer for non-English text (e.g., `jieba` for Chinese).

**Usage**:
```python
from beangulp.importers import csv
from smart_importer import PredictPostings

class MyBankImporter(csv.Importer): ...
CONFIG = [MyBankImporter(account='Assets:MyBank:MyAccount')]
HOOKS = [PredictPostings().hook]
```

**Key URLs**: [github.com/beancount/smart_importer](https://github.com/beancount/smart_importer) · [pypi.org/project/smart-importer](https://pypi.org/project/smart-importer)

---

## 6. Typical Import Flow (end-to-end)

1. **Download** statements (CSV/OFX/PDF) into a downloads folder. Beancount deliberately does no network fetching.
2. **Identify**: `python import.py identify ~/Downloads` — each importer's `identify()` tests each file.
3. **Extract**: `python import.py extract -e existing.beancount ~/Downloads > new.beancount` — matching importer converts files to directives; smart_importer predicts missing postings.
4. **Review & merge**: add missing postings/categories, dedupe (e.g., credit-card payment in both bank and card statements), append to ledger, ideally with `balance` assertions.
5. **Validate**: `bean-check ledger.beancount`.
6. **Visualize**: `fava ledger.beancount`.

---

## 7. Companion Tools (bean-* CLI family)

| Tool | Package | v3 status |
|---|---|---|
| `bean-check`, `bean-format`, `bean-example`, `bean-doctor`, `treeify` | beancount | Still in core |
| `bean-query` | beanquery | Moved out of core (0.2.0) |
| `bean-extract`, `bean-identify`, `bean-file` | beangulp (script pattern) | Old v2 tools removed; replaced by `python import.py extract\|identify\|archive` |
| `bean-report`, `bean-web`, `bean-bake` | — | Removed/deprecated in v3 |
| `bean-price` | beanprice | Split out in v3 |
| `beancount2ledger` | separate repo | Ledger-syntax converter |

### fava-edit-replay

**What it is**: A Fava extension for replaying and reviewing ledger edits. It
is useful for manual bulk-edit workflows, but it does not replace a
transaction-aware bulk transformation tool.

**This project**: Installed from
[`paulsc/fava-edit-replay`](https://github.com/paulsc/fava-edit-replay) and
configured in `main.bean`. Its local replay database is `edit_replays.yaml`.

---

## 8. Caveats

- Fava changelog page does not yet list 1.30.14 (PyPI is the source for that entry).
- beangulp last PyPI release Jan 2025; master is 0.3.0.dev0 — don't expect frequent version bumps.
- Beware third-party marketing sites (beancount.io blog / beancount.io/fava are a *commercial hosted service*); official docs are beancount.github.io.
- Any new work should target Beancount v3 to stay compatible with current Fava.
- smart_importer is officially "beta" status.

---

## 9. Investment Portfolio Management (v3-era research, 2026-08-17)

**What it is**: Beancount models investments natively — no plugin required. Fava displays holdings; analysis tools (returns, allocation) live in the ecosystem.

### Native modeling (core language, no plugins)

- `commodity` directive declares a security with metadata (`name`, `ticker`, `isin`, `quote`, `price-source`). Duplicate declarations error.
- **Cost basis & lots**: `Assets:Invest 10 VTSAX {100.00 USD}` records cost per unit; lots tracked per acquisition. Booking methods `STRICT`/`FIFO`/`LIFO`/`AVERAGE`/`NONE` set per-account in `open` or via `option "booking_method"`. See [How Inventories Work](https://beancount.github.io/docs/how_inventories_work.html).
- `price` directive records market prices (`2025-06-03 price AMZN 205.73 USD`). Prices **do not** affect booking/lot matching — they feed valuation in Fava/plugins/beanquery.
- **Capital gains**: selling `-5 AAPL {150.00 USD} @ 160.00 USD` auto-realizes P/L into a balancing income account (e.g. `Income:Capital-Gains`). See [Trading with Beancount](https://beancount.github.io/docs/trading_with_beancount.html).
- **Dividends**: plain income posting (`Assets:Brokerage:Cash 10 USD / Income:Dividends -10 USD`). No special directive.
- **Key gap**: core Beancount does not compute unrealized gains or returns. No per-share dividend database (a `distribution:` metadata feature was proposed, not implemented — [Calculating Portfolio Returns](https://beancount.github.io/docs/calculating_portolio_returns.html)).

### Price tracking

- **beanprice** (official price fetcher, PyPI 2.1.0): sources Yahoo, OANDA, ECB, Coinbase/Coincap, Alphavantage, Quandl, TSP, Chinese funds. Workflow: add `price: "USD:yahoo/AAPL"` metadata to commodity, then `bean-price --update ledger.beancount` appends `price` directives. v3-compatible. [Repo](https://github.com/beancount/beanprice) · [docs](https://beancount.github.io/docs/fetching_prices_in_beancount.html).
- `beancount.plugins.implicit_prices` (bundled): auto-generates price directives from `@` annotations in transactions.
- beangrow's `download_prices.py` backfills historical prices during returns computation.

### Investment analysis tools

| Tool | What it does | Verdict |
|---|---|---|
| **beangrow** (official) | CLI returns engine: IRR, calendar/trailing returns, dividend split, benchmarking. Basis for fava-portfolio-returns. [Repo](https://github.com/beancount/beangrow) | Worth trying |
| **fava-investor** ([Red S](https://github.com/redstreet/fava_investor)) | Asset-allocation tree, tax-loss harvesting, cash-drag, gains minimizer, ticker-util. Most complete suite; Fava extension + `investor` CLI. | Worth trying |
| **fava-portfolio-returns** ([andreasgerstmayr](https://github.com/andreasgerstmayr/fava-portfolio-returns)) | beangrow-based returns/dividends/cash-flow dashboards in Fava. | Worth trying with beangrow |
| **fava-portfolio-summary** ([PhracturedBlue](https://github.com/PhracturedBlue/fava-portfolio-summary)) | Grouped portfolio view + MWRR/TWRR. Low maintenance since 2021. | Usable, low upkeep |
| **beancount_portfolio_allocation** ([ghislainbourgeois](https://github.com/ghislainbourgeois/beancount_portfolio_allocation)) | Allocation vs. target drift report via `custom "allocation"` directives + beanquery. See §10. | Active, v3 |
| **beancount-import** ([jbms](https://github.com/jbms/beancount-import)) | Web UI for semi-automated import; OFX, Schwab CSV, StockPlanConnect. Best-in-class brokerage import. | Active |
| **beancount-lazy-plugins** ([Evernight](https://github.com/Evernight/beancount-lazy-plugins)) | Valuation plugin, opaque-fund tracking, extended balance assertions. | Active |
| **beancount-plugin-tax-uk** ([Evernight](https://github.com/Evernight/beancount-plugin-tax-uk)) | UK capital-gains tax reporting. | Active |
| **ESPPresso** | Computes ordinary income after ESPP sales; announced on mailing list Mar-2026. | Watchlist, new |

Not recommended / debunked:
- **fava-classy-portfolio** (seltzered) — v3 status unknown, niche metadata grouping.
- **portfolio-returns** (hoostus) — superseded by beangrow.
- **"beancount-investing" by ericaltendorf does NOT exist** (404; his Beancount project is **magicbeans**, crypto-tax, GPL-2.0, updated Mar-2026).

### Fava portfolio display

- **Holdings page**: positions with quantity, cost, market value, unrealized gains from `price` directives. Conversion dropdown: "At Cost", "At Market Value", "Units", "Converted to X".
- Balance sheet/income statement toggle at-cost vs at-market; built-in `portfolio_list` extension.
- **Limitations**: no built-in returns/IRR/TWRR or asset-allocation charts — use fava-investor / fava-portfolio-returns. Market value is only as good as price data. Fava ≥1.30.13 removed the `unrealized` fava-option in favor of Beancount's `account_unrealized_gains` option.

### Community patterns (2023–2026)

- **The Bean Ledger** (Yichu Zhou) — high-quality series: [Trading Stocks using Beancount](https://thebeanledger.com/posts/stock/), [RSUs](https://thebeanledger.com/posts/rsu/), [fractional-share cost basis](https://thebeanledger.com/posts/directives/) (2026-07). Examples in [flyaway1217/beancount_example](https://github.com/flyaway1217/beancount_example).
- **Lazy Beancount** — [Investments stage](https://lazy-beancount.xyz/docs/stage3_investments/overview) (stocks/ETFs/crypto end-to-end, v3-era).
- Core pattern: one account per instrument, cost on purchase, `@` price on sale, dividends to `Income:*:Dividends`.
- Ecosystem converges on **beangrow + fava-investor / fava-portfolio-returns**.

---

## 10. Portfolio Rebalancing (v3-era research, 2026-08-17)

**Key finding**: **No mature tool writes rebalancing trades into the ledger.** No PyPI package `beancount-rebalance`/`beancount-rebalancing`/`beanrebalance` exists. The ecosystem splits into (a) drift/allocation *reporting* tools and (b) generic Python rebalancers that read CSV/config, not the ledger.

### Drift/allocation tools (report only — no trades)

| Tool | URL | Activity / v3 | Input | Output |
|---|---|---|---|---|
| **beancount_portfolio_allocation** | [GitHub](https://github.com/ghislainbourgeois/beancount_portfolio_allocation) / [PyPI](https://pypi.org/project/beancount_portfolio_allocation/) | 1.0.0 Nov 2025; explicit `beancount>=3` + beanquery | Parses `.beancount` via beanquery; targets via `custom "allocation"` directives; `asset-class`/`asset-subclass` commodity metadata; `portfolio:` account metadata | Text drift report: Market Value, %, Target %, Difference |
| **fava-investor** `assetalloc_class` | [GitHub](https://github.com/redstreet/fava_investor) | v2+v3 compatible; release 1.0.1 Jan 2025 | Beancount loader; `asset_allocation_*` commodity metadata | Hierarchical allocation tree in Fava UI + `investor assetalloc-class` CLI. **No targets, no drift, no trades** |

`beancount_portfolio_allocation` usage — targets declared inline in the ledger:

```
2018-06-14 custom "allocation" "pension" "ca-stock" 30
```

Run: `bean-portfolio-allocation-report ledger.beancount --portfolio pension`. Output is per-asset-class market value vs. target vs. difference. Open issue [#4 "Target allocation percentage bands"](https://github.com/ghislainbourgeois/beancount_portfolio_allocation/issues/4) (2019) requests band-based rebalancing — unmerged.

Also: Fava's request for a rebalancing view ([fava #947](https://github.com/beancount/fava/issues/947)) was closed pointing to fava-investor — community expectation is "drift is a manual/visual exercise."

### Generic rebalancers (not Beancount-aware)

- **siavashadpey/rebalance**, **pogoetic/rebalance**, **portfolio-rebalancer-cli**, **TimeMoneyCode/portfolio-rebalancer** — Python/CLI tools taking tickers+quantities or CSV/JSON; output trade lists. No Beancount export. Mostly 2020-era or inactive.
- **tradey** ([jedimasterjonny/tradey](https://github.com/jedimasterjonny/tradey)) — consumes **Portfolio Performance** exports; rebalancing suggestions with live FX.
- **Portfolio Performance** (Java, open-source) — common companion for full portfolio analytics; rebalancing via tradey. Neither exports Beancount directives (Beancount's own [export_portfolio](https://beancount.github.io/docs/exporting_your_portfolio) report is OFX-only).
- Generic calculators: [ghostfolio-rebalancer](https://github.com/mini-maya/ghostfolio-rebalancer), [degiro-portfolio-rebalancer](https://github.com/marcopus/degiro-portfolio-rebalancer), optimalrebalancing.info (Bogleheads [Rebalancing wiki](https://www.bogleheads.org/wiki/Rebalancing)).

### Community pattern (recommended for this project)

Drift is typically computed DIY: `bean-query` / beanquery `SELECT ... value(sum(position))` grouped by account, targets kept in a separate file, and rebalancing done tax-aware by directing **new contributions** to underweight classes rather than selling. Spreadsheets are also endorsed for "what-if" scenarios (even by fava-investor's author). See [beancount.io forum "Beyond Net Worth"](https://beancount.io/forum/t/beyond-net-worth-advanced-wealth-tracking-in-beancount-unrealized-gains-allocation-drift-tax-harvesting/2624) (5% drift threshold, lot-specific selling).

**Bottom line for the user**: use **beancount_portfolio_allocation** for automated drift detection + **fava-investor** for allocation visualization. Trade generation remains a gap — a small custom script (query holdings → apply targets → print buy/sell amounts) is the pragmatic bridge, and it's a natural future plugin for this project.
