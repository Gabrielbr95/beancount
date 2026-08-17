"""Focused routing-contract tests for the B3 importer."""

from datetime import date
from decimal import Decimal
import unittest

from importers.b3 import B3Importer


XP = "XP INVESTIMENTOS CCTVM S/A"
INTER = "INTER DISTRIBUIDORA DE TITULOS E VALORES MOBILIARIOS LTDA"
TODAY = date(2026, 1, 2)


class Rows:
    """Small sheet stand-in for testing the importer row mappers."""

    def __init__(self, *rows):
        self.rows = rows

    def iter_rows(self, **_kwargs):
        return iter(self.rows)


def accounts(transaction):
    return {posting.account for posting in transaction.postings}


class B3SettlementRoutingTest(unittest.TestCase):
    def setUp(self):
        self.importer = B3Importer()

    def test_negociacoes_use_broker_cash_transfer_route(self):
        entries = self.importer._extract_negociacoes(
            "fixture.xlsx",
            Rows(
                (TODAY, "COMPRA", None, None, XP, "PETR4", 10, 10, 101),
                (TODAY, "VENDA", None, None, XP, "PETR4", 10, 10, 99),
            ),
            "Negociacao",
        )

        for entry in entries:
            self.assertIn("Equity:Transfers:XP:Cash", accounts(entry))
            self.assertNotIn("Assets:Investment:XP:Cash", accounts(entry))

    def test_xp_income_types_use_dedicated_transfer_routes(self):
        entries = self.importer._extract_movimentacoes(
            "fixture.xlsx",
            Rows(
                ("CREDITO", TODAY, "RENDIMENTO", "HGLG11", XP, 10, 1, 10),
                ("CREDITO", TODAY, "RENDIMENTO - TRANSFERIDO", "HGLG11", XP, 10, 1, 10),
                ("CREDITO", TODAY, "DIVIDENDO", "PETR4", XP, 10, 1, 10),
                ("CREDITO", TODAY, "DIVIDENDO - TRANSFERIDO", "PETR4", XP, 10, 1, 10),
                ("CREDITO", TODAY, "JUROS SOBRE CAPITAL PROPRIO", "PETR4", XP, 10, 1, 10),
                ("CREDITO", TODAY, "JUROS SOBRE CAPITAL PROPRIO - TRANSFERIDO", "PETR4", XP, 10, 1, 10),
            ),
            "Movimentacao",
        )

        routed_accounts = [
            next(account for account in accounts(entry) if account.startswith("Equity:Transfers:"))
            for entry in entries
        ]
        self.assertEqual(
            routed_accounts,
            [
                "Equity:Transfers:XP:Rendimento",
                "Equity:Transfers:XP:Rendimento",
                "Equity:Transfers:XP:Dividend",
                "Equity:Transfers:XP:Dividend",
                "Equity:Transfers:XP:JCP",
                "Equity:Transfers:XP:JCP",
            ],
        )

    def test_other_cash_events_use_broker_cash_and_custody_transfer_does_not(self):
        entries = self.importer._extract_movimentacoes(
            "fixture.xlsx",
            Rows(
                ("CREDITO", TODAY, "PAGAMENTO DE JUROS", "CDB TESTE", INTER, 10, 1, 10),
                ("CREDITO", TODAY, "DIVIDENDO", "PETR4", INTER, 10, 1, 10),
                ("CREDITO", TODAY, "LEILAO DE FRACAO", "HGLG11", INTER, 1, 10, 9),
                ("CREDITO", TODAY, "RESGATE ANTECIPADO", "CDB TESTE", INTER, 1, 10, 9),
                ("CREDITO", TODAY, "COMPRA", "CDB TESTE", INTER, 1, 10, 10),
                ("DEBITO", TODAY, "COMPRA / VENDA", "CDB TESTE", INTER, 1, 10, 9),
                ("DEBITO", TODAY, "TAXA DE CUSTODIA", "CDB TESTE", INTER, None, None, Decimal("1.23")),
                ("DEBITO", TODAY, "TRANSFERENCIA", "HGLG11", INTER, 1, None, None),
            ),
            "Movimentacao",
        )

        for entry in entries[:-1]:
            self.assertIn("Equity:Transfers:Inter:Cash", accounts(entry))
            self.assertNotIn("Assets:Investment:Inter:Cash", accounts(entry))

        transfer = entries[-1]
        self.assertIn("Equity:Transfers", accounts(transfer))
        self.assertNotIn("Equity:Transfers:Inter:Cash", accounts(transfer))


if __name__ == "__main__":
    unittest.main()
