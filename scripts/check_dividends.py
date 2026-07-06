"""Cross-check dividend payments between the B3 ledger and BRAPI event files.

Usage:
    .venv\\Scripts\\python scripts\\check_dividends.py
    .venv\\Scripts\\python scripts\\check_dividends.py --ticker PETR4 WEGE3
    .venv\\Scripts\\python scripts\\check_dividends.py --tolerance 0.02

Outputs two sections:
  - UNMATCHED EVENTS : present in one source but not the other
  - PRICE MISMATCHES : matched by (ticker, date, kind) but unit_price differs

Exit code 0 = clean. Exit code 1 = issues found.

Notes:
  - B3 rows are grouped by (asset, date, kind); total BRL and quantity are
    summed before deriving unit_price = total / quantity.
  - BRAPI rates are gross (pre-tax). B3 amounts are net (post-tax for JCP).
    Price mismatches on JCP are therefore expected until a tax factor is added.
  - Matching uses BRAPI paymentDate against the B3 transaction date.
"""

from __future__ import annotations

import argparse
import glob
import logging
import os
import re
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation

# ---------------------------------------------------------------------------
# Repo root is one level up from this script.
# ---------------------------------------------------------------------------
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN_BEAN = os.path.join(REPO_ROOT, "main.bean")
PRICES_DIR = os.path.join(REPO_ROOT, "prices")

logging.basicConfig(format="%(levelname)s: %(message)s", level=logging.WARNING)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class IncomeEvent:
    ticker: str
    event_date: date
    kind: str          # Dividend | Rendimento | JCP | Interest
    total_brl: Decimal
    quantity: Decimal
    unit_price: Decimal
    source: str        # "b3" or "brapi"


# ---------------------------------------------------------------------------
# B3 ledger side — load via beancount API
# ---------------------------------------------------------------------------

# Maps Income account category → canonical kind label
_B3_KIND_MAP = {
    "Dividend": "Dividend",
    "Rendimento": "Rendimento",
    "JCP": "JCP",
    "Interest": "Interest",
}

# Maps BRAPI label → canonical kind label
_BRAPI_KIND_MAP = {
    "DIVIDENDO": "Dividend",
    "RENDIMENTO": "Rendimento",
    "JCP": "JCP",
}


def load_b3_events(tickers: set[str] | None) -> dict[tuple, IncomeEvent]:
    """Load income events from the beancount ledger.

    Returns a dict keyed by (ticker, date, kind).
    Multiple rows with the same key are summed.
    """
    try:
        from beancount import loader
        from beancount.core import data as bcdata
    except ImportError:
        sys.exit("ERROR: beancount is not installed in this environment.")

    entries, errors, _ = loader.load_file(MAIN_BEAN)
    if errors:
        for err in errors:
            log.warning("beancount load warning: %s", err.message)

    # Accumulate: key -> (total_brl, total_quantity)
    accum: dict[tuple, list] = defaultdict(lambda: [Decimal("0"), Decimal("0")])

    for entry in entries:
        if not isinstance(entry, bcdata.Transaction):
            continue
        if entry.meta.get("source") != "b3_movimentacoes":
            continue

        ticker = entry.meta.get("asset", "")
        if not ticker:
            continue
        if tickers and ticker not in tickers:
            continue

        quantity_str = entry.meta.get("quantity")
        if not quantity_str:
            continue

        # Identify the income posting to get the kind and total BRL
        for posting in entry.postings:
            acct = posting.account
            if not acct.startswith("Income:Investment:"):
                continue
            # Account pattern: Income:Investment:<broker>:<kind>
            parts = acct.split(":")
            if len(parts) < 4:
                continue
            kind = _B3_KIND_MAP.get(parts[3])
            if kind is None:
                continue

            total_brl = abs(posting.units.number)
            try:
                qty = abs(Decimal(quantity_str))
            except InvalidOperation:
                log.warning("Bad quantity metadata on %s %s: %r", ticker, entry.date, quantity_str)
                continue

            key = (ticker, entry.date, kind)
            accum[key][0] += total_brl
            accum[key][1] += qty
            break  # only one income posting per transaction

    result: dict[tuple, IncomeEvent] = {}
    for (ticker, evt_date, kind), (total_brl, qty) in accum.items():
        if qty == 0:
            log.warning("Zero quantity for %s %s %s — skipping", ticker, evt_date, kind)
            continue
        unit_price = (total_brl / qty).quantize(Decimal("0.000001"))
        result[(ticker, evt_date, kind)] = IncomeEvent(
            ticker=ticker,
            event_date=evt_date,
            kind=kind,
            total_brl=total_brl,
            quantity=qty,
            unit_price=unit_price,
            source="b3",
        )

    return result


# ---------------------------------------------------------------------------
# BRAPI events side — parse *_events.bean files directly
# ---------------------------------------------------------------------------

# Regex to parse a brapi-cash-dividend custom directive line:
# DATE custom "brapi-cash-dividend" "ISIN" "RATE" "label=LABEL" ... "paymentDate=DATE..."
_BRAPI_LINE_RE = re.compile(
    r'^(\d{4}-\d{2}-\d{2})\s+custom\s+"brapi-cash-dividend"\s+'
    r'"[^"]*"\s+"([^"]+)"\s+.*?"label=([^"]+)".*?"paymentDate=(\d{4}-\d{2}-\d{2})',
)


def _parse_brapi_date(value: str) -> date | None:
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def load_brapi_events(tickers: set[str] | None) -> dict[tuple, IncomeEvent]:
    """Parse all prices/*_events.bean files and return income events.

    Returns a dict keyed by (ticker, paymentDate, kind).
    Multiple rows with the same key are summed (rates are additive for the
    same payment date, e.g. PETR4 sometimes splits a dividend across lines).
    """
    pattern = os.path.join(PRICES_DIR, "*_events.bean")
    files = glob.glob(pattern)
    if not files:
        sys.exit(f"ERROR: no *_events.bean files found in {PRICES_DIR}")

    accum: dict[tuple, Decimal] = defaultdict(Decimal)

    for filepath in files:
        # Derive ticker from filename: PETR4_events.bean -> PETR4
        basename = os.path.basename(filepath)
        ticker = basename.replace("_events.bean", "")
        if tickers and ticker not in tickers:
            continue

        with open(filepath, encoding="utf-8") as fh:
            for line in fh:
                m = _BRAPI_LINE_RE.match(line.strip())
                if not m:
                    continue
                _approvedOn, rate_str, label, payment_date_str = m.groups()
                payment_date = _parse_brapi_date(payment_date_str)
                if payment_date is None:
                    continue
                kind = _BRAPI_KIND_MAP.get(label.strip().upper())
                if kind is None:
                    continue  # stock dividends, unknown labels — skip
                try:
                    rate = Decimal(rate_str)
                except InvalidOperation:
                    log.warning("Bad rate in %s: %r", filepath, rate_str)
                    continue

                key = (ticker, payment_date, kind)
                accum[key] += rate

    result: dict[tuple, IncomeEvent] = {}
    for (ticker, evt_date, kind), total_rate in accum.items():
        result[(ticker, evt_date, kind)] = IncomeEvent(
            ticker=ticker,
            event_date=evt_date,
            kind=kind,
            total_brl=Decimal("0"),   # not applicable for BRAPI
            quantity=Decimal("0"),    # not applicable for BRAPI
            unit_price=total_rate.quantize(Decimal("0.000001")),
            source="brapi",
        )

    return result


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------

@dataclass
class Report:
    unmatched_b3: list[IncomeEvent] = field(default_factory=list)
    unmatched_brapi: list[IncomeEvent] = field(default_factory=list)
    price_mismatches: list[tuple[IncomeEvent, IncomeEvent, Decimal]] = field(default_factory=list)  # (b3, brapi, pct_diff)


def reconcile(
    b3: dict[tuple, IncomeEvent],
    brapi: dict[tuple, IncomeEvent],
    tolerance: Decimal,
) -> Report:
    report = Report()
    all_keys = set(b3) | set(brapi)

    for key in sorted(all_keys):
        b3_ev = b3.get(key)
        brapi_ev = brapi.get(key)

        if b3_ev and not brapi_ev:
            report.unmatched_b3.append(b3_ev)
        elif brapi_ev and not b3_ev:
            report.unmatched_brapi.append(brapi_ev)
        else:
            # Both present — compare unit prices
            if brapi_ev.unit_price == 0:
                continue
            pct_diff = abs(b3_ev.unit_price - brapi_ev.unit_price) / brapi_ev.unit_price
            if pct_diff > tolerance:
                report.price_mismatches.append((b3_ev, brapi_ev, pct_diff))

    return report


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def print_report(report: Report) -> bool:
    """Print the report. Returns True if any issues were found."""
    issues = False

    if report.unmatched_b3 or report.unmatched_brapi:
        issues = True
        print("\n-- UNMATCHED EVENTS ------------------------------------------------------")
        if report.unmatched_b3:
            print("  In B3 ledger but NOT in BRAPI:")
            print(f"  {'Ticker':<10} {'Date':<12} {'Kind':<12} {'Total BRL':>12} {'Qty':>8} {'Unit Price':>12}")
            print(f"  {'-'*10} {'-'*12} {'-'*12} {'-'*12} {'-'*8} {'-'*12}")
            for ev in sorted(report.unmatched_b3, key=lambda e: (e.ticker, e.event_date)):
                print(f"  {ev.ticker:<10} {ev.event_date!s:<12} {ev.kind:<12} {ev.total_brl:>12.4f} {ev.quantity:>8.0f} {ev.unit_price:>12.6f}")
        if report.unmatched_brapi:
            print("  In BRAPI but NOT in B3 ledger:")
            print(f"  {'Ticker':<10} {'Date':<12} {'Kind':<12} {'Rate/Share':>12}")
            print(f"  {'-'*10} {'-'*12} {'-'*12} {'-'*12}")
            for ev in sorted(report.unmatched_brapi, key=lambda e: (e.ticker, e.event_date)):
                print(f"  {ev.ticker:<10} {ev.event_date!s:<12} {ev.kind:<12} {ev.unit_price:>12.6f}")

    if report.price_mismatches:
        issues = True
        print("\n-- PRICE MISMATCHES ------------------------------------------------------")
        print(f"  {'Ticker':<10} {'Date':<12} {'Kind':<12} {'B3 Net':>12} {'BRAPI Gross':>12} {'Diff%':>8}")
        print(f"  {'-'*10} {'-'*12} {'-'*12} {'-'*12} {'-'*12} {'-'*8}")
        for b3_ev, brapi_ev, pct in sorted(report.price_mismatches, key=lambda t: (t[0].ticker, t[0].event_date)):
            print(f"  {b3_ev.ticker:<10} {b3_ev.event_date!s:<12} {b3_ev.kind:<12} {b3_ev.unit_price:>12.6f} {brapi_ev.unit_price:>12.6f} {pct*100:>7.1f}%")
        print("  NOTE: JCP mismatches are expected (B3=net after 15% IR, BRAPI=gross).")

    if not issues:
        print("OK: all events matched and prices within tolerance.")

    return issues


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cross-check B3 dividend ledger entries against BRAPI event files."
    )
    parser.add_argument(
        "--ticker", nargs="+", metavar="TICKER",
        help="Limit check to these tickers (e.g. PETR4 WEGE3). Default: all.",
    )
    parser.add_argument(
        "--tolerance", type=float, default=0.01,
        help="Allowed fractional price difference before flagging (default: 0.01 = 1%%).",
    )
    args = parser.parse_args()

    tickers = set(args.ticker) if args.ticker else None
    tolerance = Decimal(str(args.tolerance))

    print(f"Loading ledger: {MAIN_BEAN}")
    b3_events = load_b3_events(tickers)
    print(f"  {len(b3_events)} B3 income events loaded.")

    print(f"Loading BRAPI events: {PRICES_DIR}")
    brapi_events = load_brapi_events(tickers)
    print(f"  {len(brapi_events)} BRAPI cash-dividend events loaded.")

    report = reconcile(b3_events, brapi_events, tolerance)
    has_issues = print_report(report)

    sys.exit(1 if has_issues else 0)


if __name__ == "__main__":
    main()
