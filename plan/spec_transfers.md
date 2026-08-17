# Specification

## Objective
Provide a low-friction, read-only reconciliation report for exact-value cash
transfers posted through `Equity:Transfers`. The report must show which
transfer postings have a unique counterpart and which are missing or ambiguous.

## Core Requirements
- Add a standard-library Python CLI script, run from the repository root
  against `main.bean`, which loads the ledger without editing it.
- Inspect postings in `Equity:Transfers` and its child accounts, excluding
  `Equity:Transfers:Investments` and its children for this first version.
- Consider two postings candidates only when their transfer accounts and
  currencies match, their numeric amounts are equal in magnitude and opposite
  in sign, and their transaction dates are no more than four calendar days
  apart.
- Classify every inspected posting as one of:
  - **exact match**: a unique candidate, or an interchangeable same-value
    batch, is paired within the matching rules;
  - **missing counterpart**: it has no candidate; or
  - **ambiguous**: multiple non-interchangeable candidates remain.
- For repeated, otherwise identical postings, match as many opposite-sign
  postings as possible; prefer the smallest date delay and use source order as
  a stable tie-breaker. Report only unmatched leftovers as missing.
- Print a human-readable report with the posting date, transaction narration,
  transfer account, amount/currency, source file/line, and relevant candidate
  information for every result.
- Keep the default command read-only. `--apply` adds a deterministic shared
  `^auto-transfer-...` link to both transactions in each exact match.
- On a normal `--apply` pass, ignore transactions that already carry any link.
- `--apply --rewrite` re-evaluates all eligible transactions, removes only
  existing `^auto-transfer-...` links, and recreates the current exact-match
  links. It must preserve unrelated, user-authored links.
- Write source `.bean` files atomically and report every changed file. Never
  silently choose between non-exact candidates.

## Out of Scope (Crucial)
- Matching broker deposits against a group of stock trades and fees.
- Non-exact amount matching, fee tolerances, currency conversion, or
  transaction dates more than four calendar days apart.
- Changing the existing account structure or importer behavior.

## User Interaction
Run the report after imports or while reconciling transfers:

```bash
python scripts/reconcile_transfers.py main.bean
```

Review the three report sections. Resolve missing and ambiguous items manually
in the ledger. Apply newly confirmed exact matches after review:

```bash
python scripts/reconcile_transfers.py main.bean --apply
```

Regenerate this script's links across all eligible transactions only when
needed:

```bash
python scripts/reconcile_transfers.py main.bean --apply --rewrite
```
