# Architecture

## System Context
This feature adds a new phase to the loader pipeline in `loader.py`. The current pipeline in `_load()` is:

```
parse → sort → booking.book() → run_transformations (plugins) → validate
```

After this change:

```
parse → sort → run_pre_booking_plugins → booking.book() → run_transformations (plugins) → validate
```

Pre-booking plugins are invoked with the same mechanism as regular plugins (import module, find `__plugins__` functions, call with `(entries, options_map, *args)`, collect errors, sort after). The shared logic is extracted into a helper to avoid duplication.

## Data Models / State

### New option: `pre_booking_plugins`
- Stored in `options_map["pre_booking_plugins"]` as a list of `(plugin_name, plugin_config)` tuples.
- Default: `[]`.
- Converter: `options_validate_plugin` (reused from existing `plugin` option — parses `module_name` or `module_name:config`).
- NOT added to `READ_ONLY_OPTIONS` — that set blocks the `option` directive entirely, but users must be able to set `pre_booking_plugins` via `option "pre_booking_plugins" "module"`. (The existing `plugin` option is read-only only because users use the `plugin` directive instead.)

### Plugin invocation (existing, unchanged contract)
Each plugin function receives `(entries, options_map, *args)` and returns `(entries, errors)`. No change to the contract — pre-booking plugins use the exact same interface.

## Component Hierarchy
- `beancount/parser/options.py`
  - Add `Opt("pre_booking_plugins", [], ...)` to `OPTION_GROUPS`.
  - ~~Add `"pre_booking_plugins"` to `READ_ONLY_OPTIONS`.~~ (Reversed — see Data Models above.)
- `beancount/loader.py`
  - Extract plugin invocation loop from `run_transformations` into `_run_plugin_functions(plugins_iter, entries, errors, options_map, log_timings)`.
  - `run_transformations` calls `_run_plugin_functions` with the existing plugin chain.
  - New `_run_pre_booking_plugins(entries, errors, options_map, log_timings)` calls `_run_plugin_functions` with `options_map["pre_booking_plugins"]`.
  - `_load()` calls `_run_pre_booking_plugins` between sort and `booking.book()`.

## Third-Party Dependencies
- None added.
