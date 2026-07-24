# Active Context

## Resume Here
- **Tier:** Script
- **Current Slice:** Slice 5 — End-to-end verification (Pluggy importer)
- **Current Task:** N/A — all 19 tasks done except activeContext update
- **Next Action:** Commit changes. Then manually review Pluggy entries in tmp.bean and replace `Expenses:TODO` / `Income:TODO` / `Assets:TODO` counterparts with real accounts. Consider `smart_importer` hooks for automated categorization.

## Completed This Session
- Probed Pluggy API — confirmed personal access works via Meu Pluggy proxy.
- Discovered correct endpoint: `GET /v2/transactions?accountId=` (cursor-paginated). Old `/transactions` returns 410, `/v1/transactions` returns 403.
- Identified 3 item IDs → 8 accounts across Banco Inter, XP, and Banco do Brasil.
- Implemented `importers/pluggy.py` — `PluggyImporter` (beangulp.Importer subclass) with trigger-file pattern.
- Wired into `import.py` CONFIG with full account mapping.
- Added new accounts to `beans/accounts.bean`: `Assets:Investment:XP:Cash`, `Liabilities:Credit:BB:Card:EloGrafite`, `Liabilities:Credit:BB:Card:PlatinumVisa`, `Liabilities:Credit:Inter:Card`, `Expenses:TODO`, `Income:TODO`, `Assets:TODO`.
- Added `pluggy_item_ids` to `api_keys.txt`.
- Verified: 1546 Pluggy entries extracted, all balanced, zero Pluggy-related errors. Dedup confirmed (all 1546 marked duplicate on second run).

## Blockers / Open Questions
- XP duplicate transactions: both XP checking accounts return separate Pluggy txn IDs for the same underlying transaction. Within-batch dedup by Pluggy txn ID doesn't catch these. beangulp's comparator-based dedup handles it on subsequent runs against existing entries.
- Credit card transactions are mostly `PENDING` — only `POSTED` imported. Some accounts (Inter CC) have zero POSTED transactions.

## Read These First
- `plan/spec_pluggy.md`: Full specification of the Pluggy importer
- `plan/decisions_pluggy.md`: 6 decisions (trigger file, account mapping, two-posting TODO, fetch-all, credentials location, POSTED-only)
- `plan/tasks_pluggy.md`: 19 tasks, 18 done (task 19 is this update)
- `importers/pluggy.py`: The importer implementation
- `import.py`: CONFIG wiring with account mapping
