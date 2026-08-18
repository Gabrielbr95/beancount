"""Offline unit tests for importers/wise.py (WiseImporter).

Mirrors tests/test_yahoo_price_service.py: stdlib unittest, fixtures inline,
no network, no beangulp Ingest, no on-disk sample data. Fixture CSVs are
written to a TemporaryDirectory because the importer reads from the filepath.
"""

from datetime import date
import csv
import io
import os
import tempfile
import unittest

from beancount.core import data
from beancount.core.amount import Amount
from beancount.core.convert import get_weight
from beancount.core.number import D

from importers.wise import WiseImporter

# Exact 23-column Wise statement header (see export_samples/).
WISE_HEADER = (
    "TransferWise ID", "Date", "Date Time", "Amount", "Currency", "Description",
    "Payment Reference", "Running Balance", "Exchange From", "Exchange To",
    "Exchange Rate", "Payer Name", "Payee Name", "Payee Account Number",
    "Merchant", "Card Last Four Digits", "Card Holder Full Name", "Attachment",
    "Note", "Total fees", "Exchange To Amount", "Transaction Type",
    "Transaction Details Type",
)

SGD_FILENAME = "statement_152784983_SGD_2026-01-01_2026-08-18.csv"
GBP_FILENAME = "statement_108342421_GBP_2026-01-01_2026-08-18.csv"
CNY_FILENAME = "statement_107844268_CNY_2026-01-01_2026-08-18.csv"
BRL_FILENAME = "statement_51882123_BRL_2025-01-01_2025-12-31.csv"


def make_row(**overrides):
    """Build a 23-field Wise row (list of values); unset columns are empty."""
    row = {column: "" for column in WISE_HEADER}
    row.update(overrides)
    return [row[column] for column in WISE_HEADER]


def rows_to_csv(rows, header=WISE_HEADER):
    """Serialize rows into a proper quoted CSV string (header + rows)."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(header)
    writer.writerows(rows)
    return out.getvalue()


def write_csv(csv_text, directory, filename=SGD_FILENAME):
    """Write a CSV string to a temp file in ``directory`` and return its path."""
    path = os.path.join(directory, filename)
    with open(path, "w", encoding="utf-8") as f:
        f.write(csv_text)
    return path


# --- Fixture rows (modeled on export_samples/, columns only as needed) ----

CARD_ROW = make_row(
    **{
        "TransferWise ID": "CARD-4097565462",
        "Date": "23-07-2026",
        "Date Time": "23-07-2026 20:20:27.468",
        "Amount": "-27.28",
        "Currency": "SGD",
        "Description": "Transação por cartão de 21,10 USD emitida por Openrouter, Inc OPENROUTER.AI (fee: 0,06 SGD)",
        "Running Balance": "0.61",
        "Exchange From": "SGD",
        "Exchange To": "USD",
        "Exchange Rate": "0.77352",
        "Merchant": "Openrouter, Inc OPENROUTER.AI",
        "Card Last Four Digits": "2379",
        "Card Holder Full Name": "Gabriel Barros Rodrigues",
        "Total fees": "0.06",
        "Exchange To Amount": "21.10",
        "Transaction Type": "DEBIT",
        "Transaction Details Type": "CARD",
    }
)

FEE_CARD_ROW = make_row(
    **{
        "TransferWise ID": "FEE-CARD-4097565462",
        "Date": "23-07-2026",
        "Date Time": "23-07-2026 20:20:27.467",
        "Amount": "-0.06",
        "Currency": "SGD",
        "Description": "Wise Charges for: CARD-4097565462",
        "Running Balance": "27.89",
        "Merchant": "Openrouter, Inc OPENROUTER.AI",
        "Card Last Four Digits": "2379",
        "Card Holder Full Name": "Gabriel Barros Rodrigues",
        "Transaction Type": "DEBIT",
        "Transaction Details Type": "CARD",
    }
)

DEPOSIT_ROW = make_row(
    **{
        "TransferWise ID": "TRANSFER-2141742514",
        "Date": "19-05-2026",
        "Date Time": "19-05-2026 09:36:50.757",
        "Amount": "7.28",
        "Currency": "SGD",
        "Description": 'Recebeu dinheiro de RAFHAEL MARANHÃO SANTOS com a referência "118814"',
        "Payment Reference": "118814",
        "Running Balance": "147.49",
        "Payer Name": "RAFHAEL MARANHÃO SANTOS",
        "Transaction Type": "CREDIT",
        "Transaction Details Type": "DEPOSIT",
    }
)

SELF_TRANSFER_ROW = make_row(
    **{
        "TransferWise ID": "TRANSFER-2060844495",
        "Date": "05-04-2026",
        "Date Time": "05-04-2026 20:39:41.145",
        "Amount": "3700.00",
        "Currency": "GBP",
        "Description": 'Recebeu dinheiro de GABRIEL BARROS RODRIGUES com a referência "281475489979643"',
        "Payment Reference": "281475489979643",
        "Running Balance": "7434.49",
        "Payer Name": "GABRIEL BARROS RODRIGUES",
        "Transaction Type": "CREDIT",
        "Transaction Details Type": "DEPOSIT",
    }
)

CONVERSION_DEBIT_ROW = make_row(
    **{
        "TransferWise ID": "BALANCE-5232969525",
        "Date": "04-05-2026",
        "Date Time": "04-05-2026 21:09:39.117",
        "Amount": "-298.98",
        "Currency": "GBP",
        "Description": "300,00 GBP convertidos para 516,61 SGD (fee: 1,02 GBP)",
        "Running Balance": "7134.49",
        "Exchange From": "GBP",
        "Exchange To": "SGD",
        "Exchange Rate": "1.72790",
        "Total fees": "1.02",
        "Exchange To Amount": "516.61",
        "Transaction Type": "DEBIT",
        "Transaction Details Type": "CONVERSION",
    }
)

FEE_BALANCE_ROW = make_row(
    **{
        "TransferWise ID": "FEE-BALANCE-5232969525",
        "Date": "04-05-2026",
        "Date Time": "04-05-2026 21:09:39.116",
        "Amount": "-1.02",
        "Currency": "GBP",
        "Description": "Wise Charges for: BALANCE-5232969525",
        "Running Balance": "7433.47",
        "Transaction Type": "DEBIT",
        "Transaction Details Type": "CONVERSION",
    }
)

CONVERSION_CREDIT_ROW = make_row(
    **{
        "TransferWise ID": "BALANCE-5232969525",
        "Date": "04-05-2026",
        "Date Time": "04-05-2026 21:09:39.117",
        "Amount": "516.61",
        "Currency": "SGD",
        "Description": "300,00 GBP convertidos para 516,61 SGD",
        "Running Balance": "570.86",
        "Exchange From": "GBP",
        "Exchange To": "SGD",
        "Exchange Rate": "1.72790",
        "Exchange To Amount": "516.61",
        "Transaction Type": "CREDIT",
        "Transaction Details Type": "CONVERSION",
    }
)


def postings_sum_zero(txn):
    """Sum posting weights (units * price where present) must be zero."""
    total = D("0")
    for posting in txn.postings:
        number, currency = get_weight(posting)
        total += number
    return total == D("0")


class WiseIdentifyTests(unittest.TestCase):
    def test_accepts_wise_statement_filename(self):
        self.assertTrue(WiseImporter().identify(SGD_FILENAME))

    def test_rejects_unrelated_filenames(self):
        importer = WiseImporter()
        for name in ("bank.csv", "statement_foo.csv", "statement_1234_sgd.csv"):
            self.assertFalse(importer.identify(name))

    def test_rejects_wrong_currency_token_length(self):
        # Regex requires exactly 3 uppercase ASCII letters: [A-Z]{3}.
        importer = WiseImporter()
        self.assertFalse(importer.identify("statement_1234_XX_2026-01-01_2026-08-18.csv"))
        self.assertFalse(importer.identify("statement_1234_XXXX_2026-01-01_2026-08-18.csv"))
        self.assertFalse(importer.identify("statement_1234_sgd_2026-01-01_2026-08-18.csv"))


class WiseAccountTests(unittest.TestCase):
    def test_account_derives_currency_from_filename(self):
        importer = WiseImporter()
        self.assertEqual(importer.account(SGD_FILENAME), "Assets:Bank:Wise:SGD")
        self.assertEqual(importer.account(GBP_FILENAME), "Assets:Bank:Wise:GBP")


class WiseExtractTests(unittest.TestCase):
    def setUp(self):
        self.importer = WiseImporter()
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)

    # -- Empty / header-only file -----------------------------------------

    def test_header_only_file_yields_no_entries_and_no_date(self):
        path = write_csv(rows_to_csv([]), self.tmpdir.name)
        self.assertEqual(self.importer.extract(path, []), [])
        self.assertIsNone(self.importer.date(path))

    # -- CARD / DEPOSIT / TRANSFER rows -----------------------------------

    def test_card_debit_row_books_expense(self):
        path = write_csv(rows_to_csv([CARD_ROW]), self.tmpdir.name)
        entries = self.importer.extract(path, [])
        self.assertEqual(len(entries), 1)
        txn = entries[0]
        self.assertIsInstance(txn, data.Transaction)
        self.assertEqual(txn.meta["id"], "wise-SGD-CARD-4097565462")
        self.assertEqual(txn.tags, frozenset({"wise"}))
        self.assertEqual(txn.date, date(2026, 7, 23))
        self.assertEqual(txn.payee, "Openrouter, Inc OPENROUTER.AI")
        self.assertEqual(txn.narration, CARD_ROW[5])
        self.assertEqual(txn.meta["exchange_rate"], "0.77352")
        self.assertEqual(txn.meta["card_last4"], "2379")
        self.assertEqual(txn.meta["fee"], "0.06")

        self.assertEqual(len(txn.postings), 2)
        asset, expense = txn.postings
        self.assertEqual(asset.account, "Assets:Bank:Wise:SGD")
        self.assertEqual(asset.units, Amount(D("-27.28"), "SGD"))
        self.assertEqual(expense.account, "Expenses:Uncategorized:Wise")
        self.assertEqual(expense.units, Amount(D("27.28"), "SGD"))
        self.assertTrue(postings_sum_zero(txn))

    def test_deposit_credit_row_books_income(self):
        path = write_csv(rows_to_csv([DEPOSIT_ROW]), self.tmpdir.name)
        entries = self.importer.extract(path, [])
        self.assertEqual(len(entries), 1)
        txn = entries[0]
        self.assertEqual(txn.meta["id"], "wise-SGD-TRANSFER-2141742514")
        self.assertEqual(txn.payee, "RAFHAEL MARANHÃO SANTOS")
        self.assertEqual(txn.meta["payment_reference"], "118814")
        self.assertEqual(txn.postings[0].account, "Assets:Bank:Wise:SGD")
        self.assertEqual(txn.postings[0].units, Amount(D("7.28"), "SGD"))
        self.assertEqual(txn.postings[1].account, "Income:Uncategorized:Wise")
        self.assertEqual(txn.postings[1].units, Amount(D("-7.28"), "SGD"))
        self.assertTrue(postings_sum_zero(txn))

    def test_transfer_out_row_books_expense(self):
        # Outgoing transfer ("Enviou dinheiro para X") is an outflow → expense
        # placeholder. Payee comes from the Payee Name column.
        row = make_row(
            **{
                "TransferWise ID": "TRANSFER-2245953361",
                "Date": "12-07-2026",
                "Date Time": "12-07-2026 19:08:29.248",
                "Amount": "-2000.00",
                "Currency": "GBP",
                "Description": "Enviou dinheiro para RAFAEL BARROS RODRIGUES",
                "Payment Reference": "790365",
                "Running Balance": "4955.69",
                "Payee Name": "RAFAEL BARROS RODRIGUES",
                "Payee Account Number": "70457985",
                "Transaction Type": "DEBIT",
                "Transaction Details Type": "TRANSFER",
            }
        )
        path = write_csv(rows_to_csv([row]), self.tmpdir.name, GBP_FILENAME)
        entries = self.importer.extract(path, [])
        self.assertEqual(len(entries), 1)
        txn = entries[0]
        self.assertEqual(txn.meta["id"], "wise-GBP-TRANSFER-2245953361")
        self.assertEqual(txn.payee, "RAFAEL BARROS RODRIGUES")
        self.assertEqual(txn.postings[0].account, "Assets:Bank:Wise:GBP")
        self.assertEqual(txn.postings[0].units, Amount(D("-2000.00"), "GBP"))
        self.assertEqual(txn.postings[1].account, "Expenses:Uncategorized:Wise")
        self.assertEqual(txn.postings[1].units, Amount(D("2000.00"), "GBP"))
        self.assertTrue(postings_sum_zero(txn))

    def test_sign_type_mismatch_warns_but_still_imports(self):
        row = make_row(
            **{
                "TransferWise ID": "CARD-1",
                "Date": "23-07-2026",
                "Date Time": "23-07-2026 20:20:27.468",
                "Amount": "10.00",
                "Currency": "SGD",
                "Running Balance": "0.61",
                "Merchant": "Merchant Teste",
                "Transaction Type": "DEBIT",  # positive Amount + DEBIT → mismatch
                "Transaction Details Type": "CARD",
            }
        )
        path = write_csv(rows_to_csv([row]), self.tmpdir.name)
        with self.assertLogs("importers.wise", level="WARNING") as logs:
            entries = self.importer.extract(path, [])
        self.assertEqual(len(entries), 1)
        self.assertTrue(any("sign/type mismatch" in message for message in logs.output))

    # -- Self-transfer detection ------------------------------------------

    def test_self_transfer_books_to_equity(self):
        path = write_csv(rows_to_csv([SELF_TRANSFER_ROW]), self.tmpdir.name, GBP_FILENAME)
        entries = self.importer.extract(path, [])
        self.assertEqual(len(entries), 1)
        txn = entries[0]
        self.assertEqual(txn.postings[1].account, "Equity:Transfers:Wise")
        self.assertEqual(txn.postings[1].units, Amount(D("-3700.00"), "GBP"))
        self.assertTrue(postings_sum_zero(txn))

    def test_custom_self_names_match(self):
        importer = WiseImporter(self_names=["outro nome"])
        row = make_row(
            **{
                "TransferWise ID": "TRANSFER-CUSTOM",
                "Date": "19-05-2026",
                "Date Time": "19-05-2026 09:36:50.757",
                "Amount": "50.00",
                "Currency": "SGD",
                "Running Balance": "147.49",
                "Payer Name": "Outro Nome Pessoa",
                "Transaction Type": "CREDIT",
                "Transaction Details Type": "DEPOSIT",
            }
        )
        path = write_csv(rows_to_csv([row]), self.tmpdir.name)
        entries = importer.extract(path, [])
        self.assertEqual(entries[0].postings[1].account, "Equity:Transfers:Wise")

    def test_custom_self_names_replace_defaults(self):
        # With self_names=["outro nome"], the default name no longer matches.
        importer = WiseImporter(self_names=["outro nome"])
        path = write_csv(rows_to_csv([SELF_TRANSFER_ROW]), self.tmpdir.name, GBP_FILENAME)
        entries = importer.extract(path, [])
        self.assertEqual(entries[0].postings[1].account, "Income:Uncategorized:Wise")

    # -- Split-payment id namespacing (regression) --------------------------

    def test_same_card_id_in_two_currency_files_gets_distinct_ids(self):
        # Real quirk: the same card transaction (CARD-3330770788) is debited
        # from BOTH the CNY and GBP balances. Ids must be namespaced per
        # currency so id-based dedup never collapses the two entries.
        cny_row = make_row(
            **{
                "TransferWise ID": "CARD-3330770788",
                "Date": "10-01-2026",
                "Date Time": "10-01-2026 12:00:00.000",
                "Amount": "-768.77",
                "Currency": "CNY",
                "Description": "Transação por cartão de 2.797,77 CNY emitida por Alp*Taobao Shanghai",
                "Running Balance": "1000.00",
                "Merchant": "Alp*Taobao Shanghai",
                "Transaction Type": "DEBIT",
                "Transaction Details Type": "CARD",
            }
        )
        gbp_row = make_row(
            **{
                "TransferWise ID": "CARD-3330770788",
                "Date": "10-01-2026",
                "Date Time": "10-01-2026 12:00:00.000",
                "Amount": "-216.98",
                "Currency": "GBP",
                "Description": "Transação por cartão de 2.797,77 CNY emitida por Alp*Taobao Shanghai (fee: 0,78 GBP)",
                "Running Balance": "5000.00",
                "Exchange From": "GBP",
                "Exchange To": "CNY",
                "Exchange Rate": "9.35104",
                "Exchange To Amount": "2029.00",
                "Merchant": "Alp*Taobao Shanghai",
                "Transaction Type": "DEBIT",
                "Transaction Details Type": "CARD",
            }
        )
        cny_path = write_csv(rows_to_csv([cny_row]), self.tmpdir.name, CNY_FILENAME)
        gbp_path = write_csv(rows_to_csv([gbp_row]), self.tmpdir.name, GBP_FILENAME)
        cny_entries = self.importer.extract(cny_path, [])
        gbp_entries = self.importer.extract(gbp_path, [])
        self.assertEqual(cny_entries[0].meta["id"], "wise-CNY-CARD-3330770788")
        self.assertEqual(gbp_entries[0].meta["id"], "wise-GBP-CARD-3330770788")
        self.assertNotEqual(cny_entries[0].meta["id"], gbp_entries[0].meta["id"])

    # -- FEE-CARD rows ----------------------------------------------------

    def test_fee_card_row_books_bank_fee(self):
        path = write_csv(rows_to_csv([FEE_CARD_ROW]), self.tmpdir.name)
        entries = self.importer.extract(path, [])
        self.assertEqual(len(entries), 1)
        txn = entries[0]
        self.assertEqual(txn.meta["id"], "wise-SGD-FEE-CARD-4097565462")
        self.assertEqual(txn.narration, "Wise Charges for: CARD-4097565462")
        self.assertEqual(len(txn.postings), 2)
        asset, fee = txn.postings
        self.assertEqual(asset.account, "Assets:Bank:Wise:SGD")
        self.assertEqual(asset.units, Amount(D("-0.06"), "SGD"))
        self.assertEqual(fee.account, "Expenses:BankFees:Wise")
        self.assertEqual(fee.units, Amount(D("0.06"), "SGD"))
        self.assertTrue(postings_sum_zero(txn))

    # -- BALANCE_CASHBACK rows (real: monthly BRL cashback, 2025) ---------

    def test_cashback_row_books_dedicated_income(self):
        row = make_row(
            **{
                "TransferWise ID": "BALANCE_CASHBACK-531c0203-2cf0-4623-130a-ac3259d2798c",
                "Date": "03-02-2025",
                "Date Time": "03-02-2025 00:00:00.000",
                "Amount": "66.92",
                "Currency": "BRL",
                "Description": "Cashback",
                "Running Balance": "14581.31",
                "Total fees": "0.00",
                "Transaction Type": "CREDIT",
                "Transaction Details Type": "UNKNOWN",
            }
        )
        path = write_csv(rows_to_csv([row]), self.tmpdir.name, BRL_FILENAME)
        entries = self.importer.extract(path, [])
        self.assertEqual(len(entries), 1)
        txn = entries[0]
        self.assertEqual(txn.meta["id"], "wise-BRL-BALANCE_CASHBACK-531c0203-2cf0-4623-130a-ac3259d2798c")
        self.assertEqual(txn.narration, "Cashback")
        self.assertEqual(len(txn.postings), 2)
        asset, income = txn.postings
        self.assertEqual(asset.account, "Assets:Bank:Wise:BRL")
        self.assertEqual(asset.units, Amount(D("66.92"), "BRL"))
        self.assertEqual(income.account, "Income:Cashback:Wise")
        self.assertEqual(income.units, Amount(D("-66.92"), "BRL"))
        self.assertTrue(postings_sum_zero(txn))

    # -- Conversion (BALANCE) rows ----------------------------------------

    def test_conversion_debit_merges_fee_into_one_transaction(self):
        path = write_csv(
            rows_to_csv([CONVERSION_DEBIT_ROW, FEE_BALANCE_ROW]), self.tmpdir.name, GBP_FILENAME
        )
        entries = self.importer.extract(path, [])
        self.assertEqual(len(entries), 1)  # FEE-BALANCE consumed, not standalone
        txn = entries[0]
        self.assertIsInstance(txn, data.Transaction)
        self.assertEqual(txn.meta["id"], "wise-GBP-BALANCE-5232969525")
        self.assertEqual(txn.narration, "Convert GBP to SGD")

        self.assertEqual(len(txn.postings), 3)
        gbp, sgd, fee = txn.postings
        self.assertEqual(gbp.account, "Assets:Bank:Wise:GBP")
        self.assertEqual(gbp.units, Amount(D("-300.00"), "GBP"))
        self.assertEqual(sgd.account, "Assets:Bank:Wise:SGD")
        self.assertEqual(sgd.units, Amount(D("516.61"), "SGD"))
        # Total price of the destination leg: dst @@ net, i.e. per-unit price.
        self.assertEqual(sgd.price, Amount(D("298.98") / D("516.61"), "GBP"))
        self.assertEqual(fee.account, "Expenses:BankFees:Wise")
        self.assertEqual(fee.units, Amount(D("1.02"), "GBP"))
        self.assertTrue(postings_sum_zero(txn))

    def test_conversion_credit_leg_is_skipped(self):
        path = write_csv(rows_to_csv([CONVERSION_CREDIT_ROW]), self.tmpdir.name)
        entries = self.importer.extract(path, [])
        self.assertEqual(entries, [])

    def test_fee_balance_row_alone_is_not_emitted(self):
        path = write_csv(rows_to_csv([FEE_BALANCE_ROW]), self.tmpdir.name, GBP_FILENAME)
        entries = self.importer.extract(path, [])
        self.assertEqual(entries, [])

    # -- Balance assertion flag -------------------------------------------

    def test_balance_assertion_emitted_only_when_flag_set(self):
        path = write_csv(rows_to_csv([DEPOSIT_ROW]), self.tmpdir.name)
        # Flag off (default): no Balance directive.
        entries = self.importer.extract(path, [])
        self.assertFalse(any(isinstance(entry, data.Balance) for entry in entries))
        # Flag on: newest row's Running Balance at newest date + 1 day.
        importer = WiseImporter(emit_balance=True)
        entries = importer.extract(path, [])
        balances = [entry for entry in entries if isinstance(entry, data.Balance)]
        self.assertEqual(len(balances), 1)
        balance = balances[0]
        self.assertEqual(balance.date, date(2026, 5, 20))
        self.assertEqual(balance.account, "Assets:Bank:Wise:SGD")
        self.assertEqual(balance.amount, Amount(D("147.49"), "SGD"))

    # -- Format drift guard -----------------------------------------------

    def test_missing_transferwise_id_column_raises(self):
        header = [column for column in WISE_HEADER if column != "TransferWise ID"]
        path = write_csv(rows_to_csv([CARD_ROW], header=header), self.tmpdir.name)
        with self.assertRaisesRegex(ValueError, "format drift"):
            self.importer.extract(path, [])


if __name__ == "__main__":
    unittest.main()