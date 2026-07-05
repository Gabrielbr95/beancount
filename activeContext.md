# Active Context

## Resume Here
- **Tier:** Script
- **Current Slice:** Ledger cleanup / error resolution
- **Current Task:** Splits data fetching — implementation pending
- **Next Action:** Write a splits fetch script using Python `urllib` + `ssl` (with `check_hostname=False`) to hit `query1.finance.yahoo.com/v8/finance/chart/{TICKER}.SA?events=splits&range=max&interval=1mo` directly — bypasses `yfinance`/`curl_cffi` SSL issue on corporate network. Parse the `events.splits` block from the JSON response and emit beancount-formatted entries for `splits.bean`. Target tickers: WEGE3, B3SA3, BBDC3, BBAS3, FLRY3, MGLU3, ITSA3.

## Completed This Session
- Researched free B3 data sources: `yfinance` confirmed as best option (free, no auth, `.SA` suffix, full split history)
- Researched `beanprice`: decided NOT to adopt it — existing BRAPI Fava extension is superior for this setup
- Confirmed Yahoo Finance has split data for B3 tickers by manually fetching WEGE3.SA chart JSON
  - WEGE3 splits confirmed: 13:10 (2014-04-24), 2:1 (2015-04-01), 13:10 (2018-04-25), 2:1 (2021-04-28)
- Identified corporate network SSL issue: `curl_cffi` (used by `yfinance`) fails with self-signed cert in chain
  - Workaround: use `urllib` with `ssl` context (`check_hostname=False`, `verify_mode=CERT_NONE`) — no curl_cffi involved

## Blockers / Open Questions
- **20 "Not enough lots" errors** — two distinct causes:
  1. **FIIs (HGLG11, HGRU11, MCCI11, IRDM11, XPLG11, XPML11):** secondary offerings — missing buys not in exports. Need manual research.
  2. **Stocks (WEGE3, B3SA3, BBDC3, BBAS3, FLRY3, MGLU3, ITSA3):** missing split entries in `splits.bean` — script will fix this.
- **4 "Failed to categorize" errors** (CVCB11, XPBR31): malformed source data — fix manually in `transactions.bean`.
- **SSL on corporate network:** `yfinance` unusable directly. Use raw `urllib` approach for Yahoo API calls.

## Read These First
- `activeContext.md`: this file — resume point
- `splits.bean`: current split registry — incomplete, needs additions from Yahoo data
- `plugins/stock_split.py`: how splits are applied retroactively
- `prices/`: BRAPI-based price system — working, do not replace with beanprice
