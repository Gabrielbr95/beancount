# Implementation Plan

## Slice 1: Generate correctly routed B3 entries
- [x] 1. Add a small explicit transfer-account helper in `importers/b3.py`, then route each supported cash-settled B3 event to the approved route: Rendimento, Dividend, JCP, or broker Cash. Keep commodity custody transfers unchanged. (Verification: focused tests assert every event family emits the required `Equity:Transfers:<broker>:<route>` posting and no longer emits an investment cash posting.)

## Slice 2: Preserve the routing contract
- [x] 2. Add focused stdlib `unittest` coverage for the transaction-type-to-route contract, including XP income types, XP trade cash, and Inter cash/interest. (Verification: `python -m unittest discover` passes.)
- [x] 3. Update `context/b3_importer.md` to document actual account generation and the new transfer routing table. (Verification: documentation matches all supported routing branches in `importers/b3.py`.)

## Slice 3: Verify against the current importer workflow
- [x] 4. Run focused tests, syntax/compile checks, and a real B3 extraction smoke check; inspect generated entries for stale `Assets:Investment:XP:Cash` / `Assets:Investment:Inter:Cash` settlement postings. (Verification: `unittest` and `compileall` pass; 2026 B3 movement extraction emitted no legacy investment-cash postings.)
