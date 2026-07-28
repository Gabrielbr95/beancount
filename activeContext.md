# Active Context

## Resume Here
- **Tier:** Script
- **Current Slice:** pluggy.py refactor (Slice 6, Decision [018]) — complete, uncommitted
- **Current Task:** N/A — refactor done per reviewer's prioritized sequence (steps 1–5)
- **Next Action:** Commit pending changes then push. Files: `importers/pluggy.py`, `import.py`, `plan/decisions_pluggy.md`, `plan/spec_pluggy.md`, `plan/tasks_pluggy.md`, `activeContext.md`. After that, do task 24: manually reclassify existing `tmp.bean` Pluggy entries (replace `Expenses:TODO` / `Income:TODO` counterparts with real accounts) so `PredictPostings` has clean training data.

## Completed This Session
- Called adversarial reviewer on `importers/pluggy.py`. Verdict FAIL: functionally correct, but carried dead code, misleading comments, and un-tracked plan drift.
- Refactor step 1: deleted unused `from urllib.parse import urlencode` import.
- Refactor step 2: deleted `CATEGORY_MAP` dict (~70 lines) and `_map_category` static method — both unreachable post single-leg refactor. No external callers (grep-confirmed).
- Refactor step 3: removed unreachable `if status != "POSTED": return None` guard in `_build_transaction` (caller `extract` already filters); docstring rewritten — "Returns None if no amount" + "Caller is responsible for filtering on status=POSTED".
- Refactor step 4: reworded misleading "ML features" comments. `PredictPostings` default hook trains on narration/payee/day-of-month only; `pluggy_category_id` / `pluggy_category` / `pluggy_merchant` are provenance, not features. Added `# TODO: reclassify tmp.bean` near `HOOKS` in `import.py`.
- Refactor step 5: appended Decision `[018]` superseding `[014]` in `plan/decisions_pluggy.md`; amended `plan/spec_pluggy.md` §4 (single posting) and Out-of-Scope (smart_importer DONE); added Slice 6 tasks 20–24 to `plan/tasks_pluggy.md`.

## Blockers / Open Questions
- Task 24 (pending): existing ~1546 Pluggy entries in `tmp.bean` carry two-leg `Expenses:TODO` / `Income:TODO` counterparts. `PredictPostings` will learn to predict TODO accounts until these are reclassified. Unblocks trustworthy auto-categorization.
- Reviewer-flagged low-probability items NOT addressed (deferred): `_parse_date("")` raises `ValueError` (POSTED txns always have a date in practice); synthetic `id` collision risk if Pluggy omits `id` for same-date txns across accounts (Pluggy almost always sends `id`); `_parse_amount`/`_parse_date` one-line wrappers (kept for parity with `importers/b3.py`); `except Exception: log + raise` in `extract` (kept — log aids 11pm debugging); cursor-pagination 3-branch handling (kept until proven speculative against real API behavior); `load_credentials` typo tolerance (kept until `api_keys.txt` typo fixed at source).

## Read These First
- `importers/pluggy.py`: `_build_transaction` (single-leg, docstring honest about PredictPostings scope), `extract` (status filter at line 321)
- `import.py`: HOOKS with `# TODO: reclassify tmp.bean` comment, CONFIG order rationale
- `plan/decisions_pluggy.md`: Decision `[018]` (single-leg + PredictPostings, supersedes `[014]`)
- `plan/tasks_pluggy.md`: Slice 6 tasks 20–24 (20–23 done, 24 pending manual reclassification)
- `tmp.bean`: existing entries needing manual classification (task 24)
