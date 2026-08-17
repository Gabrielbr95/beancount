# Beancount Ecosystem Research

> Reference for agent conversations. Research date: **2026-08-15** (live data from PyPI/GitHub).
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
