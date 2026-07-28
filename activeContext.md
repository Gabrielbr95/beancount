# Active Context

## Resume Here
- **Tier:** Script
- **Current Slice:** ledger_csv.py built (post-refactor tool for task 24)
- **Current Task:** N/A — script built and round-trip verified, uncommitted
- **Next Action:** Commit `scripts/ledger_csv.py` when ready. Then execute task 24 workflow: `python scripts/ledger_csv.py to-csv tmp.bean tmp.csv` → edit `account` column in Excel (replace `Expenses:TODO`/`Income:TODO`/`Assets:TODO` counterparts with real accounts) → `python scripts/ledger_csv.py from-csv tmp.csv tmp_new.bean` → swap `tmp.bean` ← `tmp_new.bean` → `bean-check main.bean`. After enough reclassifications, `PredictPostings` has clean training data and future imports auto-categorize.

## Completed This Session
- Built `scripts/ledger_csv.py` — lossless round-trip between Beancount transactions and CSV. Schema discovery (not hardcoded): any txn/posting meta keys become columns, optional fields (cost, price, posting flag) appear only if used. One row per posting; synthetic `txn_id`+`posting_idx` drive regrouping. Empty cells skipped on rebuild (clear `account` cell = drop posting). Non-Transaction directives raise loudly. Inconsistent txn-level fields across rows of same txn raise loudly (use Excel fill-down). Round-trip verified on tmp.bean: 1546 txns, diff empty after whitespace normalization. Meta values stored as strings (lossless for Pluggy data; lossy in TYPE for numeric/date meta — documented).
- Earlier: Pluggy single-leg refactor + dead-code cleanup (commit c550bfa, pushed).

## Blockers / Open Questions
- Task 24 workflow now unblocked by `scripts/ledger_csv.py`. Requires manual Excel effort to reclassify ~1546 tmp.bean Pluggy entries.
- Reviewer-flagged low-probability items still deferred (from earlier refactor): `_parse_date` empty-string guard, synthetic `id` collision risk, `_parse_amount`/`_parse_date` one-line wrappers, `except+raise` in extract, cursor-pagination branch collapse, `load_credentials` typo tolerance.

## Read These First
- `scripts/ledger_csv.py`: module docstring (workflow + losslessness contract), `discover_schema` (column discovery), `build_txn` (consistency check), `build_posting` (empty-account skip)
- `importers/pluggy.py`: `_build_transaction` (single-leg, docstring honest about PredictPostings scope), `extract` (status filter at line 321)
- `import.py`: HOOKS with `# TODO: reclassify tmp.bean` comment, CONFIG order rationale
- `plan/decisions_pluggy.md`: Decision `[018]` (single-leg + PredictPostings, supersedes `[014]`)
- `plan/tasks_pluggy.md`: Slice 6 tasks 20–24 (20–23 done, 24 pending manual reclassification)
- `tmp.bean`: existing entries needing manual classification (task 24)
