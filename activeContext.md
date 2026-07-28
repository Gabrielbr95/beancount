# Active Context

## Resume Here
- **Tier:** Script
- **Current Slice:** Pluggy reclassification tooling (Slice 6, Decision [018]) — committed
- **Current Task:** N/A — code work done and pushed (commits `c550bfa`, `db0bfe9`)
- **Next Action:** Execute task 24 (manual): `python scripts/ledger_csv.py to-csv tmp.bean tmp.csv` → edit `account` column in Excel (replace `Expenses:TODO` / `Income:TODO` / `Assets:TODO` counterparts with real accounts; use fill-down to keep txn-level fields in sync across rows of same `txn_id`) → `python scripts/ledger_csv.py from-csv tmp.csv tmp_new.bean` → swap `tmp.bean` ← `tmp_new.bean` → `bean-check main.bean`. Repeat in batches until TODO counterparts are gone; `PredictPostings` then has clean training data and future imports auto-categorize.

## Completed This Session
- Pluggy single-leg refactor + dead-code cleanup (commit `c550bfa`): deleted `CATEGORY_MAP` (~70 lines) and `_map_category` from `importers/pluggy.py`; removed unreachable POSTED guard and unused `urlencode` import; reworded misleading "ML features" comments (PredictPostings trains on narration/payee/day-of-month only, not custom metadata); added `# TODO: reclassify tmp.bean` near HOOKS in `import.py`. Decision `[018]` supersedes `[014]`; `spec_pluggy.md` §4 and Out-of-Scope amended; `tasks_pluggy.md` Slice 6 added (tasks 20–24).
- Built `scripts/ledger_csv.py` (commit `db0bfe9`): lossless txn↔CSV round-trip with schema discovery. One row per posting; `txn_id`+`posting_idx` regroup; empty cells skipped on rebuild; non-Transaction directives raise loudly; txn-level field inconsistency across rows of same txn raises loudly. Round-trip on tmp.bean: 1546 txns, byte-equal on transaction content. Only diffs vs `tmp.bean`: beangulp `****` trigger marker (not a Transaction, intentionally not re-emitted) and one trailing blank line.

## Blockers / Open Questions
- Task 24 (pending): ~1546 `tmp.bean` Pluggy entries carry `Expenses:TODO` / `Income:TODO` / `Assets:TODO` counterparts. `PredictPostings` will learn to predict TODO accounts until these are reclassified. Unblocks trustworthy auto-categorization.
- Reviewer-flagged low-probability items deferred (not blocking, tracked here for awareness): `_parse_date("")` raises `ValueError` (POSTED txns always have a date in practice); synthetic `id` collision if Pluggy omits `id` for same-date txns across accounts; `_parse_amount`/`_parse_date` one-line wrappers (kept for parity with `importers/b3.py`); `except+raise` in `extract` (kept — log aids debugging); cursor-pagination 3-branch handling (kept until proven speculative); `load_credentials` typo tolerance (kept until `api_keys.txt` typo fixed at source).
- `ledger_csv.py` known limitation: meta values stored as strings. Lossless for Pluggy data; lossy in TYPE for numeric/date meta (value round-trips but beancount sees it as a string on reimport). Documented in the script's module docstring.

## Read These First
- `scripts/ledger_csv.py`: module docstring (workflow + losslessness contract + limitation), `discover_schema` (column discovery, preserves meta key order), `build_txn` (txn-level field consistency check), `build_posting` (empty-account skip)
- `importers/pluggy.py`: `_build_transaction` (single-leg, docstring honest about PredictPostings scope), `extract` (status filter at line 321)
- `import.py`: HOOKS with `# TODO: reclassify tmp.bean` comment, CONFIG order rationale
- `plan/decisions_pluggy.md`: Decision `[018]` (single-leg + PredictPostings, supersedes `[014]`)
- `plan/tasks_pluggy.md`: Slice 6 tasks 20–24 (20–23 done, 24 pending manual reclassification)
- `tmp.bean`: existing entries needing manual classification (task 24)
