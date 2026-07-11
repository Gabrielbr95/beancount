# Specification

## Objective
Add a pre-booking plugin phase to the beancount loader pipeline, allowing plugins to transform entries before lot booking occurs. This enables plugins like stock-split adjusters to fix lot sizes before booking matches reductions against inventory.

## Core Requirements
- Add a new `pre_booking_plugins` option to `options.py`, storing a list of `(plugin_name, plugin_config)` tuples, same structure as the existing `plugin` option.
- Reuse the `options_validate_plugin` converter (same syntax: `module_name` or `module_name:config`).
- Refactor the plugin invocation loop in `run_transformations` into a reusable helper function so both phases share the same import/call/error-handling logic.
- In `_load()`, run pre-booking plugins between `entries.sort()` and `booking.book()`.
- Pre-booking plugins run before booking; regular plugins continue to run after booking in `run_transformations` (unchanged).
- Respect `plugin_processing_mode`: in `"raw"` mode, only `pre_booking_plugins` run pre-booking (no preset plugins). In `"default"` mode, same — no preset plugins in pre-booking phase (presets are post-booking only).

## Out of Scope (Crucial)
- New parser directive (`plugin-pre-booking`). The user chose option (A) — an option, not a directive.
- Per-plugin `__runs_before_booking__` attribute. The phase is controlled by the user in the ledger, not by the plugin author.
- Changes to `run_transformations` behavior for existing plugins. They continue to run exactly as before.
- Changes to the booking algorithm itself.
- The `stock_split` plugin itself — it lives in the user's personal repo and is not part of this PR.

## User Interaction
Users add pre-booking plugins in their ledger:

```
option "pre_booking_plugins" "plugins.stock_split"
```

Multiple plugins with config:

```
option "pre_booking_plugins" "plugins.stock_split"
option "pre_booking_plugins" "plugins.other:config_string"
```

These plugins run after parsing and before booking, receiving `(entries, options_map)` and returning `(new_entries, errors)`, same contract as regular plugins.
