# Active Context

## Resume Here
- **Tier:** Script
- **Current Slice:** Wise (TransferWise) importer (Slice 16) — implemented, integrated, E2E-verified (tasks 1-14, i.e. `plan/tasks_wise.md` slices 1-6), offline unit tests added (task 15).
- **Current Task:** Slice 7 wrap-up — `tests/test_wise.py` written and green; `plan/tasks.md` task 51 marked done.
- **Next Action:** Slice 8, task 17 — decide how to book pre-window Wise opening balances (needs user decision). Until then the `emit_balance=False` constructor gate (default) suppresses the Balance directive; task 17 flips it to `True`. Also pending: user-side Fava UI visual confirmation of the imported Wise accounts.
- **Files touched this session:** `tests/test_wise.py` (new), `plan/tasks.md`, `activeContext.md`.

## Completed This Session
- Wrote `tests/test_wise.py` (offline, stdlib `unittest`, mirrors `tests/test_yahoo_price_service.py`): 17 tests covering `identify()`/`account()`/`date()`, header-only files, CARD DEBIT, DEPOSIT CREDIT, self-transfers (default + custom `self_names`), FEE-CARD, BALANCE DEBIT+CREDIT conversion merge, FEE-BALANCE suppression, `emit_balance` gating, and the format-drift guard. Full suite: 26/26 passed.
- Marked `plan/tasks.md` task 51 (Slice 16) `[x]`; added a note pointing to `plan/tasks_wise.md` state (7 of 8 slices done; task 17 pending user decision).
- Wise importer state entering this wrap-up: `importers/wise.py` implemented, registered in `import.py`, `beans/wise.bean` included from `main.bean`, E2E-verified — 247/247 sample rows import with `bean-check` clean, conversions merged, fees booked (tasks 1-14).

## Blockers / Open Questions
- Task 17 (Slice 8, opening balances): pre-window Wise balances unbooked. Blocked on user decision — download a full-history statement or provide known balances. `beans/opening_balances.bean` already shows the house pad-anchor pattern for mid-history accounts that task 17 can follow.
- Fava UI visual confirmation of the Wise accounts is pending (user side).
- pytest is not installed in `.venv` and the machine is offline. Tests were run via a pytest 9.0.3 binary from another project venv with this venv's site-packages on `PYTHONPATH`. Add pytest to requirements next time online.

## Read These First
- `importers/wise.py`: the Wise importer under test.
- `tests/test_wise.py`: new offline unit tests.
- `plan/tasks_wise.md`: Wise slices — 7 of 8 done; task 17 (opening balances) pending.
- `plan/decisions_wise.md`: Wise design decisions ([001]-[009]), incl. the `emit_balance` gate [007].
- `plan/tasks.md`: current task state, especially Slice 16.
- `export_samples/wise_statement_2026-01-01_2026-08-18_csv/`: the 9 per-currency Wise statement samples used for verification.
- `beans/opening_balances.bean`: pad-anchor pattern for mid-history accounts (relevant to task 17).
- `beans/wise.bean`: include target for imported Wise entries.