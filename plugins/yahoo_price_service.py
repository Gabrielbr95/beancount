"""Yahoo Finance price updater service.

Mirrors brapi_price_service.py structure exactly.
Primary source for prices, splits, and dividends.
BRAPI is retained as a dormant reference (see brapi_price_service.py).

Output files (prices_dir configurable via main.bean, default 'prices'):
  <prices_dir>/TICKER.bean         — daily close prices
  <prices_dir>/TICKER_events.bean  — splits (desdobramento/grupamento/bonificacao)
                                and dividends (dividendo, reference only)
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import yfinance as yf

from beancount.core.data import Transaction


BR_TICKER_RE = re.compile(r"^[A-Z0-9]{4,5}\d{1,2}$")
PRICE_LINE_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+price\s+(?P<ticker>[A-Z0-9]+)"
    r"\s+(?P<price>-?\d+(?:\.\d+)?)\s+(?P<currency>[A-Z0-9]+)\s*$"
)

# Split type classification — same rules used in splits.bean migration.
# ratio > 1 and integer  → desdobramento
# ratio < 1              → grupamento
# ratio > 1 and non-int  → bonificacao
def _classify_split(ratio: Decimal) -> str:
    if ratio < 1:
        return "grupamento"
    if ratio == ratio.to_integral_value() and ratio > 1:
        return "desdobramento"
    return "bonificacao"  # > 1, non-integer (e.g. 1.05, 1.1)


@dataclass(slots=True)
class PricePoint:
    price_date: date
    value: Decimal
    currency: str


@dataclass(slots=True)
class EventRecord:
    event_date: date
    directive: str
    values: list[str]


@dataclass(slots=True)
class RunSummary:
    updated: list[str] = field(default_factory=list)
    full_refresh: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    generated_files: list[str] = field(default_factory=list)


def _quote(value: Any) -> str:
    return json.dumps("" if value is None else str(value), ensure_ascii=False)


def _decimal_to_text(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return format(normalized.quantize(Decimal(1)), "f")
    return format(normalized, "f").rstrip("0").rstrip(".")


def _is_b3_ticker(ticker: str) -> bool:
    return bool(BR_TICKER_RE.match(ticker.upper()))


def _yahoo_symbol(ticker: str) -> str:
    """Append .SA suffix for B3 tickers."""
    return f"{ticker.upper()}.SA"


def _parse_asset_prices(path: Path) -> dict[date, PricePoint]:
    if not path.exists():
        return {}
    prices: dict[date, PricePoint] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = PRICE_LINE_RE.match(line.strip())
        if not match:
            continue
        try:
            line_date = date.fromisoformat(match.group("date"))
        except ValueError:
            continue
        prices[line_date] = PricePoint(
            price_date=line_date,
            value=Decimal(match.group("price")),
            currency=match.group("currency"),
        )
    return prices


def _latest_price_date(prices: dict[date, PricePoint]) -> date | None:
    return max(prices) if prices else None


def _price_map(points: list[PricePoint]) -> dict[date, PricePoint]:
    return {p.price_date: p for p in points}


def _extract_holdings(entries: list[Any]) -> dict[str, Decimal]:
    holdings: dict[str, Decimal] = {}
    for entry in entries:
        if not isinstance(entry, Transaction):
            continue
        for posting in entry.postings:
            if not posting.account.startswith("Assets:Investment:"):
                continue
            if posting.account.endswith(":Cash"):
                continue
            units = posting.units
            if units is None:
                continue
            ticker = units.currency.upper()
            holdings[ticker] = holdings.get(ticker, Decimal("0")) + Decimal(str(units.number))
    return holdings


class YahooPriceUpdater:
    def __init__(self, ledger: Any, config: dict[str, Any] | None = None) -> None:
        self.ledger = ledger
        self.config = config or {}
        self.base_dir = Path(self.ledger.beancount_file_path).parent
        self.prices_dir = self.base_dir / self.config.get("prices_dir", "prices")
        self.overlap_days = int(self.config.get("overlap_days", 7))
        self.max_assets = self.config.get("max_assets")
        # all_history: when True, fetch prices+events for every ticker that ever
        # appeared in Assets:Investment:* postings (including fully-sold ones),
        # not just currently-held tickers. Needed because historical corporate
        # actions (splits/bonuses) affect past lot cost-basis forever, so a
        # fully-sold ticker like B3SA3 still needs its _events.bean generated.
        self.all_history = bool(self.config.get("all_history", False))

    def run(self) -> RunSummary:
        summary = RunSummary()
        holdings = _extract_holdings(self.ledger.all_entries_by_type.Transaction)

        if self.max_assets is not None:
            holdings = dict(sorted(holdings.items())[: int(self.max_assets)])

        # Select tickers to update. Default (all_history=False): only currently
        # held tickers (units > 0). all_history=True: every ticker that ever
        # appeared in investment postings (net balance may be 0 for sold ones),
        # so historical corporate-action events get generated for past lots.
        target_assets: dict[str, Decimal] = {}
        for ticker, units in holdings.items():
            # all_history: include any ticker that ever had a posting (key
            # present in holdings), even if net balance is 0 (fully sold).
            # _extract_holdings only adds keys for tickers with real postings,
            # so key existence is sufficient evidence of trade history.
            include = True if self.all_history else units > 0
            if not include:
                summary.skipped.append(ticker)
                continue
            if not _is_b3_ticker(ticker):
                summary.skipped.append(ticker)
                summary.warnings.append(f"Skipped unsupported ticker: {ticker}")
                continue
            target_assets[ticker] = units

        self.prices_dir.mkdir(parents=True, exist_ok=True)

        for ticker in sorted(target_assets):
            try:
                self._update_asset_files(ticker, summary)
                summary.updated.append(ticker)
            except Exception as exc:
                summary.errors.append(f"{ticker}: {exc}")

        self._write_index(sorted(target_assets))
        summary.generated_files = [str(self.prices_dir / "prices.bean")]
        summary.generated_files.extend(
            str(self.prices_dir / f"{ticker}.bean") for ticker in sorted(target_assets)
        )
        summary.generated_files.extend(
            str(self.prices_dir / f"{ticker}_events.bean") for ticker in sorted(target_assets)
        )
        return summary

    def _update_asset_files(self, ticker: str, summary: RunSummary) -> None:
        asset_path = self.prices_dir / f"{ticker}.bean"
        events_path = self.prices_dir / f"{ticker}_events.bean"
        existing_prices = _parse_asset_prices(asset_path)
        last_price_date = _latest_price_date(existing_prices)

        symbol = _yahoo_symbol(ticker)
        yf_ticker = yf.Ticker(symbol)

        # --- Fetch price history ---
        if last_price_date is None:
            hist = yf_ticker.history(period="max", auto_adjust=False)
        else:
            overlap_start = last_price_date - timedelta(days=self.overlap_days)
            # yfinance start is inclusive
            hist = yf_ticker.history(
                start=overlap_start.isoformat(),
                end=date.today().isoformat(),
                auto_adjust=False,
            )

        if hist.empty:
            raise RuntimeError(f"Yahoo Finance returned no price data for {symbol}")

        currency = "BRL"  # All B3 tickers are BRL
        new_points = []
        for ts, row in hist.iterrows():
            # ts is a pandas Timestamp — convert to date
            price_date = ts.date() if hasattr(ts, "date") else ts.to_pydatetime().date()
            close = row.get("Close")
            if close is None or (hasattr(close, "__float__") and close != close):  # NaN check
                continue
            new_points.append(PricePoint(
                price_date=price_date,
                value=Decimal(str(round(float(close), 6))),
                currency=currency,
            ))

        new_price_map = _price_map(new_points)

        # Overlap mismatch check (same logic as BRAPI service)
        if last_price_date is not None:
            overlap_start = last_price_date - timedelta(days=self.overlap_days)
            overlap_mismatch = False
            for point in new_points:
                if point.price_date < overlap_start:
                    continue
                existing = existing_prices.get(point.price_date)
                if existing is None:
                    continue
                if abs(existing.value - point.value) > Decimal("0.0001"):
                    overlap_mismatch = True
                    break

            if overlap_mismatch:
                summary.full_refresh.append(ticker)
                full_hist = yf_ticker.history(period="max", auto_adjust=False)
                full_points = []
                for ts, row in full_hist.iterrows():
                    price_date = ts.date() if hasattr(ts, "date") else ts.to_pydatetime().date()
                    close = row.get("Close")
                    if close is None or (hasattr(close, "__float__") and close != close):
                        continue
                    full_points.append(PricePoint(
                        price_date=price_date,
                        value=Decimal(str(round(float(close), 6))),
                        currency=currency,
                    ))
                merged = _price_map(full_points)
            else:
                merged = {
                    **{d: p for d, p in existing_prices.items() if d < overlap_start},
                    **new_price_map,
                }
        else:
            merged = new_price_map

        # --- Fetch events (splits + dividends) ---
        events = self._extract_events(ticker, yf_ticker)

        self._write_asset_file(ticker, merged, currency, asset_path)
        self._write_events_file(ticker, events, events_path, currency)

    def _extract_events(self, ticker: str, yf_ticker: yf.Ticker) -> list[EventRecord]:
        events: list[EventRecord] = []

        # --- Splits ---
        try:
            splits = yf_ticker.splits  # pandas Series: index=Timestamp, value=ratio float
        except Exception:
            splits = None

        if splits is not None and not splits.empty:
            for ts, ratio_float in splits.items():
                if ratio_float == 0:
                    continue
                event_date = ts.date() if hasattr(ts, "date") else ts.to_pydatetime().date()
                ratio = Decimal(str(round(float(ratio_float), 10))).normalize()
                directive = _classify_split(ratio)
                events.append(EventRecord(
                    event_date=event_date,
                    directive=directive,
                    # Values: ticker (string), ratio (number — bare), source (string).
                    # Per beancount custom-directive syntax, numbers are bare, strings quoted.
                    values=[
                        _quote(ticker),
                        _decimal_to_text(ratio),
                        _quote("source=yahoo-splits"),
                    ],
                ))

        # --- Dividends (reference only — not used in reconcile enrichment) ---
        try:
            dividends = yf_ticker.dividends  # pandas Series: index=Timestamp, value=amount float
        except Exception:
            dividends = None

        if dividends is not None and not dividends.empty:
            for ts, amount_float in dividends.items():
                if amount_float == 0:
                    continue
                event_date = ts.date() if hasattr(ts, "date") else ts.to_pydatetime().date()
                amount = Decimal(str(round(float(amount_float), 6)))
                events.append(EventRecord(
                    event_date=event_date,
                    directive="dividendo",
                    # Values: ticker (string), amount (number — bare), source (string).
                    # Per beancount custom-directive syntax, numbers are bare, strings quoted.
                    values=[
                        _quote(ticker),
                        _decimal_to_text(amount),
                        _quote("source=yahoo-dividends"),
                    ],
                ))

        events.sort(key=lambda e: e.event_date)
        return events

    def _write_asset_file(
        self, ticker: str, prices: dict[date, PricePoint], currency: str, path: Path
    ) -> None:
        latest = _latest_price_date(prices)
        generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        lines = [
            "; source: Yahoo Finance",
            f"; asset: {ticker}",
            f"; quote_currency: {currency}",
            f"; last_update: {latest.isoformat() if latest else ''}",
            f"; generated_at: {generated_at}",
            "",
        ]
        for price_date in sorted(prices):
            point = prices[price_date]
            lines.append(
                f"{price_date.isoformat()} price {ticker} "
                f"{_decimal_to_text(point.value)} {point.currency}"
            )
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_events_file(
        self, ticker: str, events: list[EventRecord], path: Path, currency: str
    ) -> None:
        generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        latest = max((e.event_date for e in events), default=None)
        lines = [
            "; source: Yahoo Finance",
            f"; asset: {ticker}",
            f"; quote_currency: {currency}",
            f"; last_update: {latest.isoformat() if latest else ''}",
            f"; generated_at: {generated_at}",
        ]

        if events:
            lines.append("")
            for event in events:
                line = (
                    f'{event.event_date.isoformat()} custom "{event.directive}" '
                    + " ".join(event.values)
                )
                lines.append(line)
        else:
            lines.append("; no events found")

        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_index(self, tickers: list[str]) -> None:
        generated_at = datetime.now(timezone.utc).astimezone().date().isoformat()
        lines = [
            "; Auto-generated by Yahoo Finance price updater",
            f"; last_update: {generated_at}",
            "",
        ]
        for ticker in tickers:
            lines.append(f'include "{ticker}.bean"')
        (self.prices_dir / "prices.bean").write_text(
            "\n".join(lines).rstrip() + "\n", encoding="utf-8"
        )
