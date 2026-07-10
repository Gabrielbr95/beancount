"""BRAPI price updater service."""

from __future__ import annotations

import ast
import json
import os
import re
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from beancount.core.data import Transaction


BR_TICKER_RE = re.compile(r"^[A-Z]{4}\d{1,2}$")
PRICE_LINE_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})\s+price\s+(?P<ticker>[A-Z0-9]+)\s+(?P<price>-?\d+(?:\.\d+)?)\s+(?P<currency>[A-Z0-9]+)\s*$"
)


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
    tags: set[str] = field(default_factory=set)


@dataclass(slots=True)
class RunSummary:
    updated: list[str] = field(default_factory=list)
    full_refresh: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    generated_files: list[str] = field(default_factory=list)


class BrapiFeatureUnavailable(RuntimeError):
    pass


def _quote(value: Any) -> str:
    return json.dumps("" if value is None else str(value), ensure_ascii=False)


def _decimal_to_text(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return format(normalized.quantize(Decimal(1)), "f")
    return format(normalized, "f").rstrip("0").rstrip(".")


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def _safe_date_from_timestamp(timestamp: int | float) -> date:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).date()


def _is_b3_ticker(ticker: str) -> bool:
    return bool(BR_TICKER_RE.match(ticker.upper()))


def _choose_range(days: int) -> str:
    ranges = [
        (7, "7d"),
        (31, "1mo"),
        (92, "3mo"),
        (183, "6mo"),
        (366, "1y"),
        (730, "2y"),
        (1825, "5y"),
        (3650, "10y"),
    ]
    for limit, label in ranges:
        if days <= limit:
            return label
    return "max"


def _parse_asset_prices(path: Path) -> dict[date, PricePoint]:
    if not path.exists():
        return {}

    prices: dict[date, PricePoint] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = PRICE_LINE_RE.match(line.strip())
        if not match:
            continue
        line_date = _parse_date(match.group("date"))
        if line_date is None:
            continue
        prices[line_date] = PricePoint(
            price_date=line_date,
            value=Decimal(match.group("price")),
            currency=match.group("currency"),
        )
    return prices


def _latest_price_date(prices: dict[date, PricePoint]) -> date | None:
    if not isinstance(prices, dict):
        raise TypeError(f"Expected price map, got {type(prices).__name__}")
    return max(prices) if prices else None


def _price_map(points: list[PricePoint]) -> dict[date, PricePoint]:
    return {point.price_date: point for point in points}


def _load_api_key(base_dir: Path) -> str:
    env_key = os.getenv("BRAPI_API_KEY")
    if env_key:
        return env_key.strip()

    api_keys_path = base_dir / "api_keys.txt"
    if not api_keys_path.exists():
        raise FileNotFoundError("BRAPI API key not found. Add BRAPI_API_KEY or api_keys.txt")

    for line in api_keys_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("brapi") and "=" in stripped:
            _, raw_value = line.split("=", 1)
            return ast.literal_eval(raw_value.strip())

    raise FileNotFoundError("No brapi key found in api_keys.txt")


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


class BrapiPriceUpdater:
    def __init__(self, ledger: Any, config: dict[str, Any] | None = None) -> None:
        self.ledger = ledger
        self.config = config or {}
        self.base_dir = Path(self.ledger.beancount_file_path).parent
        self.prices_dir = self.base_dir / "prices"
        self.overlap_days = int(self.config.get("overlap_days", 7))
        self.initial_range = str(self.config.get("initial_range", "3mo"))
        self.full_history_range = str(self.config.get("full_history_range", "10y"))
        self.max_assets = self.config.get("max_assets")

    def run(self) -> RunSummary:
        summary = RunSummary()
        holdings = _extract_holdings(self.ledger.all_entries_by_type.Transaction)

        if self.max_assets is not None:
            holdings = dict(sorted(holdings.items())[: int(self.max_assets)])

        target_assets = {ticker: units for ticker, units in holdings.items() if units > 0}
        for ticker, units in holdings.items():
            if units <= 0:
                summary.skipped.append(ticker)
            elif not _is_b3_ticker(ticker):
                summary.skipped.append(ticker)
                summary.warnings.append(f"Skipped unsupported ticker: {ticker}")
                target_assets.pop(ticker, None)

        self.prices_dir.mkdir(parents=True, exist_ok=True)

        for ticker in sorted(target_assets):
            try:
                self._update_asset_files(ticker, summary)
                summary.updated.append(ticker)
            except Exception as exc:  # pragma: no cover - surfaced in the UI
                summary.errors.append(f"{ticker}: {exc}")

        self._write_index(sorted(target_assets))
        summary.generated_files = [str(self.prices_dir / "prices.bean")]
        summary.generated_files.extend(str(self.prices_dir / f"{ticker}.bean") for ticker in sorted(target_assets))
        summary.generated_files.extend(str(self.prices_dir / f"{ticker}_events.bean") for ticker in sorted(target_assets))
        return summary

    def _update_asset_files(self, ticker: str, summary: RunSummary) -> None:
        asset_path = self.prices_dir / f"{ticker}.bean"
        events_path = self.prices_dir / f"{ticker}_events.bean"
        existing_prices = _parse_asset_prices(asset_path)
        last_price_date = _latest_price_date(existing_prices)

        if last_price_date is None:
            remote = self._fetch_history(ticker, self.initial_range, summary)
            merged = _price_map(remote["prices"])
        else:
            overlap_start = last_price_date - timedelta(days=self.overlap_days)
            needed_days = (date.today() - overlap_start).days + 1
            remote = self._fetch_history(ticker, _choose_range(needed_days), summary)

            overlap_mismatch = False
            for point in remote["prices"]:
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
                remote = self._fetch_history(ticker, self.full_history_range, summary)
                merged = _price_map(remote["prices"])
            else:
                merged = {
                    **{d: p for d, p in existing_prices.items() if d < overlap_start},
                    **_price_map(remote["prices"]),
                }

        self._write_asset_file(ticker, merged, remote["currency"], asset_path)
        self._write_events_file(ticker, remote["events"], events_path, remote["currency"])

    def _fetch_history(
        self,
        ticker: str,
        range_label: str,
        summary: RunSummary,
        include_dividends: bool = True,
    ) -> dict[str, Any]:
        api_key = _load_api_key(self.base_dir)
        query_params = {"interval": "1d", "range": range_label}
        if include_dividends:
            query_params["dividends"] = "true"
        query = urlencode(query_params)
        request = Request(
            f"https://brapi.dev/api/quote/{ticker}?{query}",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "User-Agent": "beancount-brapi-price-updater/1.0",
            },
        )

        try:
            with urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            snippet = body[:300].replace("\n", " ")
            if include_dividends and exc.code == 403 and "FEATURE_NOT_AVAILABLE" in body:
                summary.warnings.append(
                    f"{ticker}: BRAPI plan does not include dividends/corporate events; retrying without dividends."
                )
                return self._fetch_history(ticker, range_label, summary, include_dividends=False)
            raise RuntimeError(
                f"BRAPI HTTP {exc.code} for {ticker} ({range_label}): {exc.reason}" + (f" | {snippet}" if snippet else "")
            ) from exc
        except (URLError, TimeoutError) as exc:
            raise RuntimeError(f"BRAPI request failed for {ticker} ({range_label}): {exc}") from exc

        results = payload.get("results") or []
        if not results:
            raise RuntimeError(f"BRAPI returned no results for {ticker}")

        result = results[0]
        currency = str(result.get("currency") or "BRL")
        prices = [
            PricePoint(
                price_date=_safe_date_from_timestamp(item["date"]),
                value=Decimal(str(item["close"])),
                currency=currency,
            )
            for item in result.get("historicalDataPrice", [])
            if item.get("date") is not None and item.get("close") is not None
        ]
        prices.sort(key=lambda point: point.price_date)
        events = self._extract_events(result, ticker) if include_dividends else []
        return {"currency": currency, "prices": prices, "events": events}

    def _extract_events(self, result: dict[str, Any], ticker: str) -> list[EventRecord]:
        _LABEL_MAP = {
            "DESDOBRAMENTO": "desdobramento",
            "GRUPAMENTO": "grupamento",
            "BONIFICACAO": "bonificacao",
            "DIVIDENDO": "dividendo",
            "JCP": "jcp",
            "RENDIMENTO": "rendimento",
        }
        dividend_data = result.get("dividendsData") or {}
        events: list[EventRecord] = []

        for item in dividend_data.get("cashDividends", []) or []:
            event_date = _parse_date(item.get("paymentDate")) or _parse_date(item.get("lastDatePrior"))
            if event_date is None:
                continue
            label = item.get("label") or ""
            directive = _LABEL_MAP.get(label.upper(), "brapi-cash-dividend")
            values = [
                _quote(ticker),
                _decimal_to_text(Decimal(str(item.get("rate") or "0"))),
                _quote(f"label={label}"),
                _quote(f"approvedOn={item.get('approvedOn') or ''}"),
            ]
            if "lastDatePrior" in item:
                values.append(_quote(f"lastDatePrior={item.get('lastDatePrior') or ''}"))
            values.append(_quote(f"paymentDate={item.get('paymentDate') or ''}"))
            values.append(_quote(f"isinCode={item.get('isinCode') or ''}"))
            events.append(
                EventRecord(
                    event_date=event_date,
                    directive=directive,
                    values=values,
                    tags={"brapi"},
                )
            )

        for item in dividend_data.get("stockDividends", []) or []:
            event_date = _parse_date(item.get("approvedOn")) or _parse_date(item.get("lastDatePrior"))
            if event_date is None:
                continue
            label = item.get("label") or ""
            directive = _LABEL_MAP.get(label.upper(), "brapi-stock-dividend")
            values = [
                _quote(ticker),
                _decimal_to_text(Decimal(str(item.get("factor") or "0"))),
                _quote(f"label={label}"),
                _quote(f"approvedOn={item.get('approvedOn') or ''}"),
                _quote(f"lastDatePrior={item.get('lastDatePrior') or ''}"),
            ]
            if "paymentDate" in item:
                values.append(_quote(f"paymentDate={item.get('paymentDate') or ''}"))
            values.append(_quote(f"isinCode={item.get('isinCode') or ''}"))
            events.append(
                EventRecord(
                    event_date=event_date,
                    directive=directive,
                    values=values,
                    tags={"brapi"},
                )
            )

        events.sort(key=lambda event: event.event_date)
        return events

    def _write_asset_file(self, ticker: str, prices: dict[date, PricePoint], currency: str, path: Path) -> None:
        latest = _latest_price_date(prices)
        generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        lines = [
            "; source: BRAPI",
            f"; asset: {ticker}",
            f"; quote_currency: {currency}",
            f"; last_update: {latest.isoformat() if latest else ''}",
            f"; generated_at: {generated_at}",
            "",
        ]
        for price_date in sorted(prices):
            point = prices[price_date]
            lines.append(f"{price_date.isoformat()} price {ticker} {_decimal_to_text(point.value)} {point.currency}")
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_events_file(self, ticker: str, events: list[EventRecord], path: Path, currency: str) -> None:
        generated_at = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
        latest = max((event.event_date for event in events), default=None)
        lines = [
            "; source: BRAPI",
            f"; asset: {ticker}",
            f"; quote_currency: {currency}",
            f"; last_update: {latest.isoformat() if latest else ''}",
            f"; generated_at: {generated_at}",
        ]

        if events:
            lines.append("")
            for event in events:
                tag_str = " ".join(f"^{t}" for t in sorted(event.tags)) if event.tags else ""
                line = f'{event.event_date.isoformat()} custom "{event.directive}" ' + " ".join(event.values)
                if tag_str:
                    line += f"  {tag_str}"
                lines.append(line)
        else:
            lines.append("; no corporate events available for current BRAPI plan")

        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    def _write_index(self, tickers: list[str]) -> None:
        generated_at = datetime.now(timezone.utc).astimezone().date().isoformat()
        lines = [
            "; Auto-generated by BRAPI price updater",
            f"; last_update: {generated_at}",
            "",
        ]
        for ticker in tickers:
            lines.append(f'include "{ticker}.bean"')
        (self.prices_dir / "prices.bean").write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
