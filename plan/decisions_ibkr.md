# Decision Log — IBKR Integration

> Feature choice locked in the top-level log as Decision [013] (uabean importer).
> This file holds the IBKR-specific implementation decisions.

## [001] Manual Flex XML export (offline) over automated Flex Web Service download
- **Date:** 2026-08-17
- **Context:** uabean consumes Flex Query XML. The XML can be downloaded manually
  from IBKR Client Portal or fetched programmatically via the Flex Web Service
  (token + queryId, `ibflex[web]` client).
- **Options Considered:**
  - A: Manual export from Client Portal — zero connectivity at import time,
    no token management, works on the corporate Windows laptop.
  - B: `ibflex[web]` downloader script — fully automated but adds a token to
    manage (it lapses), a network call at runtime, and another moving part.
- **Decision:** Option A — manual export for v1.
- **Rationale:** Fits the local-first constraint and the existing pluggy/B3
  manual-trigger workflow. The Flex token adds ceremony without reducing risk
  for a monthly cadence. Revisit if the cadence gets annoying.

## [002] Account naming consistent with existing ledger conventions
- **Date:** 2026-08-17
- **Context:** uabean defaults to `Assets:Investments:IB:*` (plural "Investments").
  The ledger uses `Assets:Investment:*`, `Income:Investment:*`,
  `Expenses:Investment:*` (singular).
- **Options Considered:**
  - A: Use uabean defaults — zero config, but inconsistent naming across the
    ledger and a future migration headache.
  - B: Configure the importer with the ledger's singular convention:
    `Assets:Investment:IBKR:*`, `Income:Investment:IBKR:*`,
    `Expenses:Investment:IBKR:*`.
- **Decision:** Option B — configure the importer.
- **Rationale:** The ledger is long-lived and internally consistent; matching
  the existing convention beats saving two constructor lines. `IBKR` chosen as
  the top segment to avoid confusion with the existing `IB`-free structure and
  to leave room for future broker integrations.

## [003] Register IBKR importer in import.py CONFIG — Superseded by [006]
- **Date:** 2026-08-17
- **Context:** `import.py` already wires B3 + Pluggy into one beangulp Ingest
  and writes to `tmp.bean`, then `reconcile_actions.py` routes entries. uabean's
  IBKR importer produces finished transactions that do not need the reconcile
  routing/enrichment pass.
- **Options Considered:**
  - A: Add the IBKR importer to `import.py` CONFIG — single entry point, but
    IBKR entries land in `tmp.bean` and flow through the B3-oriented reconcile
    logic, risking misclassification.
  - B: Dedicated `import_ibkr.py` writing directly to `beans/ibkr.bean` — one
    importer, one output file, zero interaction with the existing pipeline.
- **Decision:** Option B — dedicated entry point.
- **Rationale:** Keeps the new integration isolated and reviewable. The existing
  B3/Pluggy pipeline is load-bearing and battle-tested; do not entangle it with
  a new source that has a different output shape (finished two-leg txns + balance
  directives vs single-leg txns needing enrichment).
- **Superseded by [006]** — Fava loads importers only from `import.py`'s CONFIG,
  so a dedicated entry point broke the Fava import UI (file showed as
  non-importable). Registering in `import.py` CONFIG is required.

## [006] Register IBKR importer in import.py CONFIG (Fava-compatible)
- **Date:** 2026-08-17
- **Context:** Fava loads importers exclusively from `import.py`'s CONFIG
  (`fava-option "import-config" "import.py"` in main.bean). The dedicated
  `import_ibkr.py` approach (decision [003]) worked for the CLI but Fava marked
  IBKR XML as non-importable — reproduced live with a real Flex export.
- **Options Considered:**
  - A: Register the IBKR importer in `import.py` CONFIG — one registry for CLI
    and Fava. Entries flow through `tmp.bean` like B3/Pluggy. `reconcile_actions.py`
    routing is not disturbed because IBKR transactions are complete two-leg
    transactions with their own metadata (id/isin/ib_cost), not single-leg
    TODO-counterpart entries that need routing.
  - B: Point Fava's import-config at a separate `import_ibkr.py` — would work,
    but then B3/Pluggy importers would be invisible to Fava.
- **Decision:** Option A — register in `import.py` CONFIG.
- **Rationale:** One CONFIG list is simpler than two entry points; Fava remains
  the primary import surface. `import_ibkr.py` is not created; no `beans/ibkr.bean`
  include is needed — entries flow through `tmp.bean` exactly like the other
  importers. Constructor uses the ledger's singular `Investment` naming
  (decision [002]).

## [004] Single-leg deposits/withdrawals completed manually post-extract
- **Date:** 2026-08-17
- **Context:** uabean emits deposits/withdrawals as single-leg transactions
  (payee "self"). bean-check rejects unbalanced transactions, so each needs a
  counterpart.
- **Options Considered:**
  - A: Let the importer guess the counterpart — wrong for IBKR because the
    counterpart is an external bank account (BB/Inter/XP/Wise), never known to
    the importer.
  - B: Accept single-leg output and manually add the counterpart after each
    extract (same pattern as the existing Pluggy TODO-counterpart workflow).
- **Decision:** Option B — manual completion.
- **Rationale:** The counterpart is genuinely external knowledge (which BRL bank
  account funded the USD IBKR cash). A default guess would be wrong and silently
  pollute the ledger. Manual completion is a 30-second task per transfer.

## [005] Vendor the uabean IBKR importer instead of installing the package
- **Date:** 2026-08-17
- **Context:** Installing uabean as a package drags in its full dependency tree
  (`requests`, `openpyxl`, `xlrd`, a git-master `beangulp` pin, a git-commit
  `ibflex` pin) — most of it only needed by importers we will never use
  (Monobank, Sensebank, Privatbank, XLS-based ones, etc.). The IBKR module
  itself only imports `beangulp` (+ its identifier mixin, already installed),
  `beancount` (already installed), `ibflex`, and uabean's own small
  `IdentifyMixin`.
- **Options Considered:**
  - A: Install uabean with `--no-deps` + manual `ibflex` — keeps the whole
    package on disk, still gets upstream updates, but leaves unused importers
    in site-packages and keeps the git-master beangulp risk latent.
  - B: Vendor only `ibkr.py` + `IdentifyMixin` into the project's `importers/`,
    install only `ibflex`. Matches the project's local-importer pattern
    (`importers/b3.py`, `importers/pluggy.py`). No upstream auto-updates.
- **Decision:** Option B — vendor the importer (MIT, attribution kept).
- **Rationale:** "Challenge every dependency" (AGENTS.md). The unused uabean
  surface adds install risk (git-master beangulp could replace the working
  0.2.0) for zero benefit. Vendored code is ~700 lines, self-contained, and
  lives next to the other local importers. Trade-off accepted: manual
  re-sync from upstream if a bug fix matters.