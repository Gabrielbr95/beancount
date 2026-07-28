# Decision Log

## [012] Trigger file pattern for API-based importer
- **Date:** 2026-07-17
- **Context:** beangulp is file-oriented (`identify(filepath)`, `extract(filepath)`),
  but Pluggy is a REST API with no file to parse. Need to bridge the two models.
- **Options Considered:**
  - A: Trigger file — importer `identify()`s an empty `.pluggy` sentinel file;
    `extract()` calls the API instead of reading file content.
  - B: Standalone fetch script writes JSON cache; a second beangulp importer
    reads the JSON. Two-step pipeline.
  - C: Bypass beangulp entirely — standalone script outputs `.bean` directly.
    Loses dedup, CLI, Fava integration.
- **Decision:** Option A — trigger file.
- **Rationale:** Simplest approach that preserves beangulp integration (dedup,
  CLI, Fava). One step, no intermediate files. The trigger file is just a
  sentinel — all configuration (credentials, item IDs, account mapping) lives
  in `api_keys.txt` and `import.py` CONFIG. Pattern is well-established in the
  beancount community for API-based importers.

## [013] Account mapping via constructor config dict
- **Date:** 2026-07-17
- **Context:** 8 Pluggy accounts across 3 items need mapping to Beancount
  accounts. The mapping is structural configuration (Pluggy account ID →
  Beancount account name), not a secret.
- **Options Considered:**
  - A: Hardcoded dict inside the importer class — inflexible, requires code
    changes to update.
  - B: Config dict in `import.py` CONFIG, passed to constructor — matches
    existing B3Importer pattern (`account_root` param).
  - C: Separate YAML config file — adds a file and a dependency (pyyaml) for
    minimal benefit.
- **Decision:** Option B — config dict in `import.py` CONFIG.
- **Rationale:** Consistent with existing patterns. The mapping is committed to
  git (structural, not secret — Pluggy account IDs are meaningless without the
  API key). pyyaml is already in requirements.txt but using it for this adds
  unnecessary indirection. A plain Python dict is simpler and type-safe.

## [014] Two-posting transactions with TODO counterpart
- **Date:** 2026-07-17
- **Context:** Pluggy transactions have one signed amount but no Beancount
  expense/income category. Need to decide how to model the counterpart posting.
- **Options Considered:**
  - A: Two postings — known account + `Expenses:TODO` / `Income:TODO`. Passes
    bean-check, explicit, easy to find and fix. smart_importer cannot augment
    (it needs single-posting transactions).
  - B: Single posting — smart_importer can predict the counterpart. But
    bean-check fails without smart_importer, and the auto-balanced account
    is not controllable.
  - C: Use Pluggy `category` field to map to expense accounts — brittle,
    categories don't map 1:1 to Beancount accounts, requires maintenance.
- **Decision:** Option A — two postings with `Expenses:TODO` / `Income:TODO`.
- **Rationale:** Script tier prioritizes reliability. Produces valid beancount
  out of the box. If smart_importer is added later, the switch to single-posting
  is mechanical (remove the TODO posting). The Pluggy `category` and `merchant`
  fields are stored in metadata for future categorization logic.

## [015] Fetch all transactions on each run (no incremental sync)
- **Date:** 2026-07-17
- **Context:** Pluggy `/v2/transactions` supports `dateFrom`/`dateTo` filtering.
  Could track last import date and only fetch new transactions.
- **Options Considered:**
  - A: Fetch all transactions every time — simple, relies on beangulp dedup.
  - B: Track last import date in a state file, only fetch new — faster on
    subsequent runs, but adds state management complexity.
- **Decision:** Option A — fetch all.
- **Rationale:** Largest account has ~163 transactions. Full fetch is trivially
  fast. beangulp's built-in dedup (against existing entries) handles duplicates.
  Date filtering can be added later if volume grows. No state file to manage
  or corrupt.

## [016] Credentials and item IDs in api_keys.txt
- **Date:** 2026-07-17
- **Context:** Pluggy credentials (`clientId`, `clientSecret`) already in
  `api_keys.txt` (gitignored). Item IDs need a home.
- **Options Considered:**
  - A: Item IDs in `import.py` CONFIG — committed to git. Item IDs are UUIDs,
    not secrets, but still personal configuration.
  - B: Item IDs in `api_keys.txt` (gitignored) — keeps all Pluggy config in
    one place, already gitignored.
  - C: Item IDs in the trigger file — per-run control, but adds file parsing.
- **Decision:** Option B — item IDs in `api_keys.txt`.
- **Rationale:** Keeps all Pluggy-specific configuration in one gitignored file.
  The importer reads `api_keys.txt` for both credentials and item IDs. Account
  mapping stays in `import.py` (structural, committed). Simple file format:
  `pluggy_item_ids = id1,id2,id3`.

## [017] Only POSTED transactions imported; PENDING skipped
- **Date:** 2026-07-17
- **Context:** Pluggy transactions have a `status` field: `POSTED` or `PENDING`.
  Pending transactions may change or be cancelled.
- **Options Considered:**
  - A: Import only POSTED — stable, no mutation risk.
  - B: Import both, flag PENDING in metadata — more data, but pending txns
    may disappear or change, causing dedup confusion.
- **Decision:** Option A — POSTED only.
- **Rationale:** Pending transactions are unreliable. Importing only posted
  transactions ensures the ledger is stable. Skipped pending transactions will
  appear on the next run once they post. Loud log message for skipped count.

## [018] Switch to single-leg postings + PredictPostings for Pluggy
- **Date:** 2026-07-27
- **Status:** Supersedes [014].
- **Context:** Decision [014] chose two-leg postings with `Expenses:TODO` /
  `Income:TODO` counterparts. This blocked Pluggy/B3 dedup: the heuristic
  comparator rejected pairs because Pluggy's generic `Income:Investment:Interest`
  (mapped from `CATEGORY_MAP`) was not a subset of B3's broker-specific
  `Income:Investment:XP:Rendimento`. Two-leg account sets never matched.
  Separately, `smart_importer`'s `PredictPostings` requires single-leg postings
  to predict the counterpart — it cannot augment an existing two-leg txn.
- **Options Considered:**
  - A: Keep two-leg TODO, fix dedup comparator to ignore TODO accounts —
    fragile, doesn't enable auto-categorization.
  - B: Switch to single-leg; let `PredictPostings` predict the counterpart
    from existing ledger classifications (narration, payee, day-of-month).
    Requires training data: existing ~1546 Pluggy entries in `tmp.bean` must
    be manually reclassified away from `Expenses:TODO`/`Income:TODO` first,
    or the hook will learn to predict TODO accounts.
  - C: Use Pluggy `category` field to map directly — brittle, doesn't match
    Beancount account granularity, requires manual `CATEGORY_MAP` maintenance.
- **Decision:** Option B — single-leg + PredictPostings.
- **Rationale:** Removes the dedup blocker (single-leg Pluggy posting is a
  subset of any B3 two-leg posting). Auto-categorizes future imports once
  training data is clean. Pluggy `category`/`merchant` metadata retained as
  provenance only — the default `PredictPostings` hook does not consume
  custom metadata fields. `CATEGORY_MAP` and `_map_category` removed from
  `importers/pluggy.py` as dead code post-refactor.
