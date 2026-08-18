from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import pandas as pd

from beancount.core.data import Price, Transaction
from beancount.core.number import D
from beancount.core.amount import Amount
from beancount.core.data import Posting

from plugins.yahoo_price_service import (
    CurrencyPair,
    YahooPriceUpdater,
    _extract_currencies,
    _plan_currency_pairs,
)


class YahooCurrencyPriceTests(unittest.TestCase):
    def test_discovers_currency_codes_without_tickers(self):
        posting = Posting(
            account="Assets:Cash",
            units=Amount(D("10"), "USD"),
            cost=None,
            price=None,
            flag=None,
            meta={},
        )
        transaction = Transaction(
            meta={},
            date=date(2026, 8, 18),
            flag="*",
            payee=None,
            narration="cash",
            tags=frozenset(),
            links=frozenset(),
            postings=[posting],
        )
        currencies = _extract_currencies(
            [
                transaction,
                Price({}, date(2026, 8, 18), "VWRA", Amount(D("120"), "USD")),
            ]
        )
        self.assertEqual(currencies, {"USD"})

    def test_plans_direct_target_pairs_once(self):
        pairs = _plan_currency_pairs({"ARS", "BRL", "GBP", "SGD", "USD"})
        self.assertEqual(
            [(pair.base, pair.quote) for pair in pairs],
            [
                ("ARS", "BRL"),
                ("ARS", "USD"),
                ("GBP", "BRL"),
                ("GBP", "USD"),
                ("SGD", "BRL"),
                ("SGD", "USD"),
                ("USD", "BRL"),
            ],
        )

    def test_currency_pair_uses_yahoo_symbol_and_filename(self):
        pair = CurrencyPair("USD", "BRL")
        self.assertEqual(pair.symbol, "USDBRL=X")
        self.assertEqual(pair.filename, "USD_BRL.bean")

    def test_rejects_wrong_reported_quote_currency(self):
        ticker = type(
            "FakeTicker",
            (),
            {"history_metadata": {"instrumentType": "CURRENCY", "currency": "USD"}},
        )()
        with self.assertRaisesRegex(RuntimeError, "expected BRL"):
            YahooPriceUpdater._validate_currency_metadata(ticker, CurrencyPair("USD", "BRL"))

    def test_extracts_daily_closes_and_skips_nan(self):
        history = pd.DataFrame(
            {"Close": [5.2, float("nan"), 5.3]},
            index=pd.to_datetime(["2026-08-17", "2026-08-18", "2026-08-19"]),
        )
        points = YahooPriceUpdater._extract_fx_points(history)
        self.assertEqual([point.price_date for point in points], [date(2026, 8, 17), date(2026, 8, 19)])

    def test_writes_pair_file_in_beancount_price_syntax(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "USD_BRL.bean"
            YahooPriceUpdater._write_currency_file(
                CurrencyPair("USD", "BRL"),
                {date(2026, 8, 18): D("5.2042")},
                path,
            )
            self.assertIn("2026-08-18 price USD 5.2042 BRL", path.read_text())


if __name__ == "__main__":
    unittest.main()
