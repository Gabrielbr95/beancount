# Active Context

## Resume Here
- **Tier:** Application
- **Current Slice:** N/A — pre-booking plugins feature is complete and merged to master
- **Current Task:** N/A
- **Next Action:** In `my_beancount`, commit the uncommitted changes (`stock_split.py` fix, `requirements.txt` pointing to `@master`, ledger changes). Then reinstall beancount from `@master` in the new venv: `pip install -r requirements.txt --upgrade`. Verify with `python -c "from beancount.parser.options import OPTIONS_DEFAULTS; print('pre_booking_plugins' in OPTIONS_DEFAULTS)"`. After that, test `stock_split` end-to-end with a real ledger using `option "pre_booking_plugins" "plugins.stock_split"`.

## Completed This Session
- Implemented pre-booking plugins feature (all 4 slices, 9 tasks) on branch `feature/pre-booking-plugins` in the `beancount` fork.
- Extracted `_run_plugin_functions` helper from `run_transformations` in `loader.py`.
- Added `pre_booking_plugins` option to `options.py` (reuses `options_validate_plugin`).
- Wired pre-booking phase into `_load()` between `entries.sort()` and `booking.book()`.
- Added 4 tests in `loader_test.py` (`TestPreBookingPlugins`). Full suite: 1135 tests pass.
- **Design correction (Decision [004]):** `pre_booking_plugins` must NOT be in `READ_ONLY_OPTIONS` — that set blocks the `option` directive in the parser. Reversed and documented.
- Fixed `stock_split.py` for pre-booking compatibility: handles `CostSpec` (pre-booking) vs `Cost` (post-booking), guards against `units.number is None`, updated usage docstring.
- Merged both feature branches (`feature/average-booking-method` and `feature/pre-booking-plugins`) into `master` with `--no-ff` merge commits. Pushed to `origin/master`.
- Updated `my_beancount/requirements.txt` to point to `@master` instead of `@feature/average-booking-method`.

## Blockers / Open Questions
- `my_beancount` repo has uncommitted changes: `plugins/stock_split.py`, `requirements.txt`, `main.bean`, `.main.bean.picklecache`. Need to commit before migrating.
- End-to-end test of `stock_split` with a real ledger not yet done.

## Read These First
- `plan/tasks.md`: All 9 tasks marked `[x]` (Task 2 notes the READ_ONLY_OPTIONS reversal)
- `plan/decisions.md`: Decision [004] explains why `pre_booking_plugins` is NOT in `READ_ONLY_OPTIONS`
- `plan/architecture.md`: Pipeline diagram and component hierarchy
- `beancount/loader.py:604-632`: The pre-booking phase in `_load()`
- `beancount/loader.py:680-762`: The extracted `_run_plugin_functions` helper
- `my_beancount/plugins/stock_split.py`: The consumer plugin (fixed for CostSpec compatibility, uncommitted)
- `my_beancount/requirements.txt`: Now points to `@master` (uncommitted)
