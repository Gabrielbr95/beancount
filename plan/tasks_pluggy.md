# Implementation Plan — Pluggy Importer

## Slice 1: Pluggy API client functions
- [x] 1. Write `load_credentials(path)` — parse `api_keys.txt`, return dict with `client_id`, `client_secret`, `item_ids` (list). Handle the existing typo `pluggy_cient_secret`. (Verification: call from REPL, confirm 3 item IDs parsed from `pluggy_item_ids` line)
- [x] 2. Write `authenticate(client_id, client_secret)` — `POST /auth`, return API key. Raise on non-200 with response body. (Verification: call from REPL, confirm 200 + apiKey string returned)
- [x] 3. Write `fetch_accounts(api_key, item_id)` — `GET /accounts?itemId=`, return list of account dicts. (Verification: call for all 3 item IDs, confirm 8 accounts total)
- [x] 4. Write `fetch_transactions(api_key, account_id)` — `GET /v2/transactions?accountId=`, follow cursor pagination via `next` field, return full list. (Verification: call for XP account `ffd6004e...`, confirm 163 transactions returned across all pages)

## Slice 2: PluggyImporter class skeleton
- [x] 5. Write `PluggyImporter` class in `importers/pluggy.py` — `__init__(self, account_map, credentials_file, ...)`. Store config. Subclass `beangulp.Importer`. (Verification: class instantiates without error, `name` property returns `"Pluggy Importer"`)
- [x] 6. Implement `identify(filepath)` — return True if filename ends with `.pluggy`. (Verification: `identify("export/pluggy.trigger")` returns True; `identify("export/movimentacao.xlsx")` returns False)
- [x] 7. Implement `account(filepath)` — return `"Assets:Bank"`. Implement `date(filepath)` — return today's date (placeholder, refined in Slice 3). Implement `filename(filepath)` — return `f"{date:%Y-%m-%d}.pluggy.bean"`. (Verification: all three return non-empty strings)
- [x] 8. Implement `extract(filepath, existing)` scaffold — call `authenticate`, loop item IDs, call `fetch_accounts` + `fetch_transactions`, log counts. Return empty entry list for now. (Verification: run `python import.py extract export/` with a `.pluggy` trigger file — no errors, log shows account/transaction counts)

## Slice 3: Transaction → Beancount mapping
- [x] 9. Write `_map_account(pluggy_account_id)` — look up in `account_map`, return Beancount account string. Raise `ValueError` if not found. (Verification: lookup a known ID returns correct account; unknown ID raises)
- [x] 10. Write `_parse_date(pluggy_date_str)` — extract date from ISO string `2026-07-10T23:59:59.000Z` → `date(2026, 7, 10)`. (Verification: `_parse_date("2026-07-10T03:00:00.000Z")` returns `date(2026, 7, 10)`)
- [x] 11. Write `_build_transaction(txn, pluggy_account_id, filepath, lineno)` — construct `data.Transaction` with two postings: (1) mapped account + signed amount, (2) `Expenses:TODO` for debits / `Income:TODO` for credits. Metadata: `id=pluggy-{txn_id}`, `source=pluggy`, `pluggy_category`, `pluggy_merchant`. Narration from `description`. Payee from `merchant.name` if present. Skip if `status != POSTED`. (Verification: feed a sample Pluggy txn dict, confirm valid `data.Transaction` with balanced postings)
- [x] 12. Wire `_build_transaction` into `extract()` — for each account, fetch transactions, build entries, accumulate. Update `date()` to return the max transaction date. Sort entries by date. (Verification: run extract, inspect tmp.bean — transactions present with correct accounts, amounts, and metadata)

## Slice 4: Configuration & integration
- [x] 13. Add `pluggy_item_ids` line to `api_keys.txt` with the 3 item IDs. (Verification: `load_credentials()` parses 3 IDs)
- [x] 14. Define account mapping in `import.py` CONFIG — add `PluggyImporter(account_map={...})` to CONFIG list. Map all 8 Pluggy accounts to Beancount accounts. (Verification: `import.py` loads without import errors; CONFIG has both B3 and Pluggy importers)
- [x] 15. Open any missing Beancount accounts in `beans/accounts.bean` (or rely on `auto_accounts` plugin). At minimum: `Assets:Bank:XP:Cash`, `Expenses:TODO`, `Income:TODO`. (Verification: `bean-check main.bean` passes after including tmp.bean with Pluggy entries)

## Slice 5: End-to-end verification
- [x] 16. Run full extract: `python import.py extract export/ > tmp.bean` with trigger file. Confirm both B3 and Pluggy entries in tmp.bean. (Verification: grep tmp.bean for `pluggy` in metadata — Pluggy txns present)
- [x] 17. Run `bean-check` on a ledger including tmp.bean. Confirm zero errors. (Verification: `bean-check main.bean` exits 0)
- [x] 18. Run extract twice — confirm beangulp dedup marks second run's entries as duplicates. (Verification: second extract output shows dedup warnings, no duplicate entries)
- [x] 19. Update `activeContext.md` with Pluggy importer summary and remaining open items. (Verification: file updated and readable)
