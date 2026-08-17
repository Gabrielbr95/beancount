# Active Context

## Resume Here
- **Tier:** Script
- **Current Slice:** Exact cash-transfer reconciliation (Slice 1) — report complete.
- **Current Task:** `plan/tasks_transfers.md` task 4 (pending) — decide whether a later workflow should add links to reviewed pairs.
- **Next Action:** After each import, run `python scripts/reconcile_transfers.py main.bean` to review the report, then `python scripts/reconcile_transfers.py main.bean --apply` to link new exact matches. Use `--apply --rewrite` only to regenerate this script's `^auto-transfer-*` links across all eligible transactions. Separately, task 24 remains manual: `python scripts/ledger_csv.py to-csv tmp.bean tmp.csv` → edit the relevant `leg_N_account` Excel column (for `tmp.bean`, normally `leg_2_account`) to replace `Expenses:TODO` / `Income:TODO` / `Assets:TODO` counterparts → `python scripts/ledger_csv.py from-csv tmp.csv tmp_new.bean` → swap `tmp.bean` ← `tmp_new.bean` → `bean-check main.bean`.

## Completed This Session
- Pluggy single-leg refactor + dead-code cleanup (commit `c550bfa`): deleted `CATEGORY_MAP` (~70 lines) and `_map_category` from `importers/pluggy.py`; removed unreachable POSTED guard and unused `urlencode` import; reworded misleading "ML features" comments (PredictPostings trains on narration/payee/day-of-month only, not custom metadata); added `# TODO: reclassify tmp.bean` near HOOKS in `import.py`. Decision `[018]` supersedes `[014]`; `spec_pluggy.md` §4 and Out-of-Scope amended; `tasks_pluggy.md` Slice 6 added (tasks 20–24).
- Updated `scripts/ledger_csv.py`: CSV now has one row per transaction, with postings in numbered `leg_N_*` columns. It discovers the maximum leg count, retains each populated leg on reimport, requires unique `txn_id` values, and clearly rejects the old one-row-per-posting CSV shape. Verified on `tmp.bean`: 1,546 transaction rows and all postings retained; a three-leg in-memory round-trip also passes.
- Diagnosed `tmp_pluggy.bean` → `tmp_pluggy.csv`: `-e main.bean` caused Beangulp to comment out 1,548 duplicate entries. `ledger_csv.py` correctly exported the remaining 76 active Transaction directives as 76 CSV rows; commented duplicate text is not a Beancount Transaction and is intentionally not exported.
- Disabled (but retained) Smart Importer in `import.py`: its import and hook registration are commented out. Upstream Smart Importer does not safely support this combined bank-and-card Pluggy importer (issue #130 open; no released fix).
- Added `scripts/reconcile_transfers.py`: read-only exact-match report for `Equity:Transfers:Card` and `Equity:Transfers:General`, excluding investment transfers. It requires the same transfer account and currency, equal-and-opposite amount, and ≤4 calendar-day delay; identical-value batches are paired by nearest date, then source order. `main.bean` currently reports 79 exact matches and 10 missing counterparts.
- Applied 79 `^auto-transfer-*` links to 158 matching `tmp.bean` transactions. Normal `--apply` skips any already linked transaction; `--apply --rewrite` removes and recreates only this script's reserved links, leaving other links untouched.
- Probed the live Pluggy API for 2025-07-10. BB checking's BRL 2,000.00 same-person transfer and BB savings's BRL 2,000.00 deposit form a high-confidence pair, but Pluggy exposes no shared transfer/counterpart ID. Decision [019] documents the evidence and conservative-only recommendation.

## Blockers / Open Questions
- Task 24 (pending): ~1546 `tmp.bean` Pluggy entries carry `Expenses:TODO` / `Income:TODO` / `Assets:TODO` counterparts. `PredictPostings` will learn to predict TODO accounts until these are reclassified. Unblocks trustworthy auto-categorization.
- Smart Importer is intentionally disabled. Do not use it with the current combined Pluggy importer; a per-source-account import workflow is required before revisiting automated second-leg prediction.
- Reviewer-flagged low-probability items deferred (not blocking, tracked here for awareness): `_parse_date("")` raises `ValueError` (POSTED txns always have a date in practice); synthetic `id` collision if Pluggy omits `id` for same-date txns across accounts; `_parse_amount`/`_parse_date` one-line wrappers (kept for parity with `importers/b3.py`); `except+raise` in `extract` (kept — log aids debugging); cursor-pagination 3-branch handling (kept until proven speculative); `load_credentials` typo tolerance (kept until `api_keys.txt` typo fixed at source).
- `ledger_csv.py` known limitation: meta values stored as strings. Lossless for Pluggy data; lossy in TYPE for numeric/date meta (value round-trips but beancount sees it as a string on reimport). Documented in the script's module docstring.

## Read These First
- `scripts/ledger_csv.py`: module docstring (workflow + losslessness contract + limitation), `discover_schema` (column discovery and max leg count), `build_txn` (rebuilds numbered legs), `build_posting` (empty leg-account skip)
- `scripts/reconcile_transfers.py`: read-only cash-transfer report; use after imports and before manually resolving transfer counterparts.
- `plan/spec_transfers.md`, `plan/decisions_transfers.md`, `plan/tasks_transfers.md`: exact-transfer report scope, rules, and follow-on work.
- `importers/pluggy.py`: `_build_transaction` (single-leg, docstring honest about PredictPostings scope), `extract` (status filter at line 321)
- `import.py`: HOOKS with `# TODO: reclassify tmp.bean` comment, CONFIG order rationale
- `plan/decisions_pluggy.md`: Decision `[018]` (single-leg + PredictPostings, supersedes `[014]`)
- `plan/tasks_pluggy.md`: Slices 6–7 (task 24 is manual reclassification; task 26 is the pending transfer-detection implementation)
- `plan/decisions_pluggy.md`: Decision `[019]` (live API evidence, limits, and safe proposed pairing rule)
- `tmp.bean`: existing entries needing manual classification (task 24)
