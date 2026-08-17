# Decision Log

## [001] Conservative exact-match transfer reconciliation
- **Date:** 2026-08-16
- **Context:** Independently imported bank, card, and transfer transactions
  use `Equity:Transfers` as a clearing account. Posting dates can differ, so
  account balance alone cannot identify which entries belong together.
- **Options Considered:** A: automatically pair and write links using a broad
  date/amount heuristic; B: report exact, uniquely determined candidates and
  leave all ledger edits to review; C: include broker investment settlements
  immediately.
- **Decision:** Option B. Match only equal-and-opposite amounts in the same
  transfer account and currency within four calendar days, and report unique,
  missing, and ambiguous results. Exclude `Equity:Transfers:Investments` for
  now.
- **Rationale:** Date delays make exact value matching useful, but repeated
  transfers make automatic pairing unsafe. Broker funding is commonly
  one-to-many because a deposit may settle several trades and fees, so it needs
  a separate reconciliation design. A report is reversible and fits the
  user-approved review-first workflow.

## [002] Pair interchangeable repeated transfers deterministically
- **Date:** 2026-08-16
- **Context:** The bank limits automated transfers to BRL 2,000 per
  transaction. A larger planned transfer therefore creates several
  same-day, same-value postings, which the initial unique-only rule reports as
  ambiguous even though the individual pair identity has no bookkeeping value.
- **Options Considered:** A: keep every repeated value ambiguous; B: pair
  repeated exact values in an arbitrary but stable order; C: pair the maximum
  number while preferring the smallest date delay and source order only as a
  tie-breaker.
- **Decision:** Option C. Within an account/currency/absolute-amount group,
  pair as many opposite-sign postings as the four-day rule permits. Report
  unmatched leftovers as missing; retain ambiguity only for candidates that
  cannot safely be treated as interchangeable.
- **Rationale:** This removes useless ambiguity from bank-imposed split
  transfers while remaining read-only. Nearest-date matching is more sensible
  than a naïve first-match loop when otherwise identical transfers occur across
  several days.

## [003] Opt-in, idempotent transfer links
- **Date:** 2026-08-16
- **Context:** Exact transfer matches need durable Beancount links, but the
  report reads a top-level ledger whose matching transactions may live in
  generated or included source files. Re-running the tool must not duplicate
  links or erase links created for other purposes.
- **Options Considered:** A: write links during every report run; B: make link
  writing opt-in and skip already linked transactions; C: rewrite every link
  on every run.
- **Decision:** Option B. `--apply` adds deterministic links with the reserved
  `^auto-transfer-...` prefix only to currently unlinked exact matches. The
  default remains read-only. `--apply --rewrite` removes and rebuilds only the
  reserved links across all eligible transactions, preserving all unrelated
  links.
- **Rationale:** This is low-friction for the normal import → review → apply
  workflow while containing the destructive operation behind explicit flags.
  The reserved prefix gives the script a safe ownership boundary for rewrite.
