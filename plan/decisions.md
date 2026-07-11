# Decision Log

## [001] Option-based registration over directive or attribute
- **Date:** 2026-07-10
- **Context:** Need a way for users to register plugins that run before booking. Three approaches considered: (A) new option `pre_booking_plugins`, (B) per-plugin `__runs_before_booking__` attribute, (C) new `plugin-pre-booking` directive.
- **Options Considered:** A (option) vs B (attribute) vs C (directive).
- **Decision:** Option A — a new `pre_booking_plugins` option.
- **Rationale:** User's explicit choice. It's the least invasive: no parser/grammar changes, no plugin author changes, reuses the existing `options_validate_plugin` converter, and is visible in the ledger.

## [002] Reuse options_validate_plugin converter
- **Date:** 2026-07-10
- **Context:** The `pre_booking_plugins` option needs to parse `module_name` or `module_name:config` strings into `(name, config)` tuples, same as the existing `plugin` option.
- **Decision:** Reuse `options_validate_plugin` directly.
- **Rationale:** DRY. Identical syntax and semantics. No reason to diverge.

## [003] No preset plugins in pre-booking phase
- **Date:** 2026-07-10
- **Context:** In `"default"` mode, the post-booking phase chains `PLUGINS_PRE`, user plugins, `PLUGINS_AUTO`, `PLUGINS_POST`. Should the pre-booking phase also have presets?
- **Decision:** No presets in pre-booking phase. Only user-registered `pre_booking_plugins` run.
- **Rationale:** Presets (`documents`, `pad`, `balance`) are inherently post-booking concerns. Running them before booking would break their assumptions. The pre-booking phase is opt-in only.

## [004] Do NOT add pre_booking_plugins to READ_ONLY_OPTIONS
- **Date:** 2026-07-11
- **Context:** The original architecture plan said to add `"pre_booking_plugins"` to `READ_ONLY_OPTIONS`. During implementation, tests showed that `READ_ONLY_OPTIONS` in `grammar.py` blocks the `option` directive entirely — the parser rejects `option "pre_booking_plugins" "..."` with "Option may not be set". The existing `plugin` option is in this set only because users use the `plugin` directive instead.
- **Decision:** Do NOT add `pre_booking_plugins` to `READ_ONLY_OPTIONS`. Users must be able to set it via the `option` directive (decision [001] chose option over directive).
- **Rationale:** The original plan conflated "read-only" (can't be re-modified by plugins) with "blocked from user input" (what `READ_ONLY_OPTIONS` actually does). Since there is no `pre-booking-plugin` directive, the `option` directive is the only user-facing entry point. Blocking it would make the feature unusable.
