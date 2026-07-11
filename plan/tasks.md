# Implementation Plan

## Slice 1: Add `pre_booking_plugins` option
- [x] 1. Add `pre_booking_plugins` Opt to `OPTION_GROUPS` in `options.py` with `options_validate_plugin` converter and default `[]` (Verification: `OPTIONS_DEFAULTS["pre_booking_plugins"]` equals `[]`)
- [x] 2. ~~Add `"pre_booking_plugins"` to `READ_ONLY_OPTIONS`~~ **REVERSED:** `pre_booking_plugins` must NOT be in `READ_ONLY_OPTIONS` — that set blocks the `option` directive, but the spec requires users to set it via `option "pre_booking_plugins" "module"`. The `plugin` option is read-only only because users use the `plugin` directive instead. (Design error caught during testing.)

## Slice 2: Extract reusable plugin runner
- [x] 3. Extract the plugin invocation loop from `run_transformations` into `_run_plugin_functions(plugins_iter, entries, errors, options_map, log_timings)` in `loader.py` (Verification: `run_transformations` delegates to `_run_plugin_functions` with the existing plugin chain)
- [x] 4. Verify no behavior change — run loader tests (Verification: `python -m unittest beancount.loader_test` passes, 32 tests OK)

## Slice 3: Run pre-booking plugins in `_load()`
- [x] 5. Add call to `_run_plugin_functions` with `options_map["pre_booking_plugins"]` in `_load()` between `entries.sort()` and `booking.book()`, wrapped in `misc_utils.log_time` (Verification: `_load()` source shows the call in the correct position)
- [x] 6. Verify pre-booking plugins run before booking — write a test plugin that modifies entries and confirm booking sees the modified entries (Verification: test passes)

## Slice 4: Tests and regression
- [x] 7. Write test: `option "pre_booking_plugins" "module"` registers a plugin that runs before booking (Verification: test asserts plugin ran and option parsed correctly)
- [x] 8. Write test: pre-booking plugin errors are collected and returned (Verification: test asserts errors appear in output)
- [x] 9. Run full beancount test suite (Verification: `python -m unittest discover -s beancount -p "*_test.py"` passes — 1135 tests OK, no regressions)
