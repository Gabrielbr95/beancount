# Active Context

## Resume Here
- **Tier:** Application
- **Current Slice:** N/A — pre-booking plugins feature complete
- **Current Task:** N/A
- **Next Action:** Review the diff and commit. Then test the `stock_split` plugin end-to-end with a real ledger using `option "pre_booking_plugins" "plugins.stock_split"`.

## Completed This Session
- Implemented pre-booking plugins feature on branch `feature/pre-booking-plugins` (uncommitted):
  - Slice 1: Added `pre_booking_plugins` option to `OPTION_GROUPS` in `options.py`.
  - Slice 2: Extracted `_run_plugin_functions` helper from `run_transformations` in `loader.py`.
  - Slice 3: Wired pre-booking plugin phase into `_load()` between `entries.sort()` and `booking.book()`.
  - Slice 4: Added 4 tests in `loader_test.py` (TestPreBookingPlugins). Full suite: 1135 tests pass, no regressions.
- **Design correction (Decision [004]):** Reversed Task 2 — `pre_booking_plugins` must NOT be in `READ_ONLY_OPTIONS`. That set blocks the `option` directive in the parser, which would make the feature unusable. Updated `plan/architecture.md`, `plan/spec.md`, `plan/tasks.md`, and logged in `plan/decisions.md`.
- Fixed `stock_split.py` for pre-booking compatibility: handles `CostSpec` (pre-booking) vs `Cost` (post-booking), guards against `units.number is None`, updated usage docstring to `option "pre_booking_plugins" "plugins.stock_split"`.

## Blockers / Open Questions
- None. Feature is implementation-complete; needs commit + end-to-end test with real ledger.

## Read These First
- `plan/tasks.md`: All 9 tasks marked `[x]` (Task 2 notes the reversal)
- `plan/decisions.md`: Decision [004] explains the READ_ONLY_OPTIONS reversal
- `beancount/loader.py:604-632`: The new pre-booking phase in `_load()`
- `beancount/loader.py:680-762`: The extracted `_run_plugin_functions` helper
- `/home/gabriel/Documents/Projects/my_beancount/plugins/stock_split.py`: The consumer plugin (fixed for CostSpec compatibility)
