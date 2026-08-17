# Implementation Plan — Exact Transfer Reconciliation

## Slice 1: Review exact cash-transfer candidates
- [x] 1. Add `scripts/reconcile_transfers.py` to load a ledger and collect eligible `Equity:Transfers` postings while excluding `Equity:Transfers:Investments`. (Verification: `main.bean` produced 168 eligible postings; all 312 investment-transfer postings were excluded)
- [x] 2. Classify each eligible posting using same-currency, equal-and-opposite amount, and four-calendar-day candidate rules within the same transfer account; require mutual uniqueness for a confirmed pair. (Verification: run the report on `main.bean` and inspect its unique, missing, and ambiguous categories)
- [x] 3. Print a read-only report of unique matches, missing counterparts, and ambiguous candidates with enough source context for manual review. (Verification: `python scripts/reconcile_transfers.py main.bean` produced all three labelled sections: 46 unique pairs, 7 missing counterparts, and 69 ambiguous postings; it did not modify a ledger file)
- [x] 4. Pair interchangeable repeated exact transfers, maximising matches within the four-day rule and preferring the nearest dates; report only unmatched leftovers as missing. (Verification: same-day BRL 2,000 batches now pair; `main.bean` reports 79 exact matches, 10 missing counterparts, and no ambiguous candidates)

## Slice 2: Reconcile confirmed transfer pairs
- [x] 5. Decide whether a later workflow should add shared Beancount links to reviewed pairs. (Verification: Decision [003] records opt-in `--apply` and `--apply --rewrite` behavior)
- [x] 6. Add opt-in `--apply` link writing for currently unlinked exact matches and `--rewrite` regeneration for this script's reserved links. (Verification: applied 79 links to 158 `tmp.bean` transactions; a second normal apply changed 0 transactions; rewrite regenerated 79 links; `bean-check main.bean` passed after both writes)

## Slice 3: Reconcile investment settlements
- [ ] 7. Scope bank-to-broker deposits against grouped trade and fee postings in `Equity:Transfers:Investments`. (Verification: define grouping, fee, and date-delay rules before implementation)
