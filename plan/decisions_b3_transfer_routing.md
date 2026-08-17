# Decision Log

## [001] Route B3 settlements through broker-specific transfer accounts
- **Date:** 2026-08-17
- **Context:** The B3 importer sends every BRL settlement to `Assets:Investment:<broker>:Cash`. The ledger strategy instead models B3 reports as one side of an external movement, with the matching bank or broker report providing the other side through `Equity:Transfers`.
- **Options Considered:**
  - A: Keep one generic `Equity:Transfers:Investments` account for every B3 cash event.
  - B: Route by broker and transaction type: dedicated XP income routes and a broker-specific Cash route for all other cash settlement.
- **Decision:** Option B. `Rendimento`, `Dividend`, and `JCP` use dedicated XP routes. Trades, fixed-income transactions, fees, fraction auctions, redemptions, and interest payments use `Equity:Transfers:<broker>:Cash`, including `XP` and `Inter`.
- **Rationale:** The dedicated income routes preserve the B3 event type for matching and review. The generic Cash route correctly covers cash settlement without inventing a category for every event. Broker-specific routes avoid mixing XP and Inter movements.

## [002] Leave custody transfers on the existing commodity transfer path
- **Date:** 2026-08-17
- **Context:** B3 `TRANSFERENCIA` events move securities between custodians, not BRL cash. The importer already represents them as commodity stubs against `Equity:Transfers` and merges matching in/out rows.
- **Options Considered:**
  - A: Apply the new BRL routing helper to all transfer-related events.
  - B: Limit it to BRL settlement events and leave commodity custody transfers unchanged.
- **Decision:** Option B.
- **Rationale:** The new routes are for reconciling cash movements. Changing the custody-transfer representation would conflate two different mechanisms and risk breaking existing pairing behaviour.
