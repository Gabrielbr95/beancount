"""Wise statement CSV importer for Beancount.

Converts the per-currency statement CSVs exported from Wise
(statement_<balanceId>_<CURRENCY>_<from>_<to>.csv) into Beancount entries.
Follows the house style of importers/pluggy.py (plain beangulp.Importer +
stdlib csv). Design decisions in plan/decisions_wise.md ([001]-[009]).
"""

from __future__ import annotations

import csv
import logging
import os
import re
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

import beangulp
from beancount.core import amount, data

logger = logging.getLogger(__name__)

# User's own name variants, used to detect self-transfers (decision [006]).
# Matched case-insensitively as substrings against Payer/Payee Name.
DEFAULT_SELF_NAMES = ["GABRIEL BARROS RODRIGUES", "Gabriel Barros Rodrigues"]

_FILENAME_RE = re.compile(
    r"^statement_\d+_([A-Z]{3})_\d{4}-\d{2}-\d{2}_\d{4}-\d{2}-\d{2}\.csv$"
)

# DEBIT-leg conversion description, e.g.
#   "300,00 GBP convertidos para 516,61 SGD (fee: 1,02 GBP)"
_CONVERT_RE = re.compile(r"([\d.,]+) ([A-Z]{3}) convertidos para ([\d.,]+) ([A-Z]{3})")
_FEE_RE = re.compile(r"fee: ([\d.,]+) ([A-Z]{3})")


def _parse_date(value: str) -> date:
    """Parse a Wise CSV date, day-first DD-MM-YYYY."""
    return datetime.strptime(value.strip(), "%d-%m-%Y").date()


def _parse_br_decimal(value: str) -> Decimal:
    """Parse a pt-BR formatted number ('1.181,00') into a Decimal."""
    value = value.strip()
    if "," in value:
        # Dots are thousands separators, comma is the decimal separator.
        value = value.replace(".", "").replace(",", ".")
    return Decimal(value)


class WiseImporter(beangulp.Importer):
    """beangulp importer for Wise per-currency statement CSVs.

    account() derives the currency-specific account from the filename, so a
    single instance handles every currency file.
    """

    def __init__(
        self,
        account_root: str = "Assets:Bank:Wise",
        self_names: Optional[list[str]] = None,
        emit_balance: bool = False,
    ) -> None:
        self.account_root = account_root.rstrip(":")
        self._self_names = [n.lower() for n in (self_names or DEFAULT_SELF_NAMES)]
        self.emit_balance = emit_balance

    @property
    def name(self) -> str:
        return "Wise Importer"

    def identify(self, filepath: str) -> bool:
        return bool(_FILENAME_RE.match(os.path.basename(filepath)))

    def _currency_from_filename(self, filepath: str) -> str:
        """Extract the currency token from the Wise filename."""
        m = _FILENAME_RE.match(os.path.basename(filepath))
        if not m:
            raise ValueError(f"Wise filename does not match expected pattern: {filepath}")
        return m.group(1)

    def account(self, filepath: str) -> str:
        return f"{self.account_root}:{self._currency_from_filename(filepath)}"

    def date(self, filepath: str) -> Optional[date]:
        rows = self.read_rows(filepath)
        if not rows:
            return None
        return max(_parse_date(row["Date"]) for row in rows)

    def filename(self, filepath: str) -> Optional[str]:
        max_date = self.date(filepath)
        return f"{max_date:%Y-%m-%d}.wise.bean" if max_date else None

    def read_rows(self, filepath: str) -> list[dict[str, Any]]:
        """Parse the CSV into a list of row dicts (empty for header-only files)."""
        with open(filepath, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if "TransferWise ID" not in (reader.fieldnames or []):
                raise ValueError(
                    f"Wise CSV format drift: missing 'TransferWise ID' column in {filepath}"
                )
            return list(reader)

    def extract(
        self, filepath: str, existing: list[data.Directive]
    ) -> list[data.Directive]:
        logger.info("Starting Wise import: %s", filepath)
        rows = self.read_rows(filepath)
        if not rows:
            logger.info("Finished Wise import: %s (0 rows → 0 entries)", filepath)
            return []

        currency = self._currency_from_filename(filepath)
        account = self.account(filepath)

        # BALANCE ids present in this file (conversion legs). Used to detect
        # orphan FEE-BALANCE rows whose parent conversion is missing.
        balance_ids = {
            r["TransferWise ID"][len("BALANCE-"):]
            for r in rows
            if r["TransferWise ID"].startswith("BALANCE-")
        }

        entries: list[data.Directive] = []
        for lineno, row in enumerate(rows, start=2):  # line 1 is the header
            txn_id = row["TransferWise ID"]
            if txn_id.startswith("BALANCE-"):
                entry = self._build_conversion(row, currency, account, filepath, lineno, rows)
            elif txn_id.startswith("FEE-BALANCE-"):
                # Consumed by the conversion builder (decision [004]). An
                # orphan fee whose parent BALANCE row is missing must not
                # vanish silently.
                parent = txn_id[len("FEE-BALANCE-"):]
                if parent not in balance_ids:
                    logger.warning(
                        "wise: orphan FEE-BALANCE row with no parent BALANCE "
                        "conversion in this file: %s", txn_id,
                    )
                continue
            elif txn_id.startswith("FEE-CARD-"):
                entry = self._build_fee_txn(row, currency, account, filepath, lineno)
            elif txn_id.startswith("BALANCE_CASHBACK-"):
                entry = self._build_cashback_txn(row, currency, account, filepath, lineno)
            else:
                entry = self._build_txn(row, currency, account, filepath, lineno)
            if isinstance(entry, list):
                entries.extend(entry)
            elif entry is not None:
                entries.append(entry)

        # Balance assertion (decision [007]): newest row's Running Balance at
        # that date + 1 day. Rows are newest-first, so the newest row is rows[0].
        # Gated by the emit_balance constructor flag (default False): opening
        # balances are deferred to task 17, so the ledger's Wise accounts are
        # not anchored yet and an assertion would fail every bean-check run.
        if self.emit_balance:
            newest = rows[0]
            entries.append(
                data.Balance(
                    data.new_metadata(filepath, 2),
                    _parse_date(newest["Date"]) + timedelta(days=1),
                    account,
                    amount.Amount(Decimal(newest["Running Balance"]), currency),
                    None, None,
                )
            )
        else:
            logger.info("wise: balance assertion skipped (emit_balance=False)")

        entries.sort(key=data.entry_sortkey)
        logger.info(
            "Finished Wise import: %s (%d rows → %d entries)", filepath, len(rows), len(entries)
        )
        return entries

    # -----------------------------------------------------------------------
    # Transaction builders
    # -----------------------------------------------------------------------

    def _is_self_transfer(self, row: dict[str, Any]) -> bool:
        """True if the row's Payer/Payee Name is one of the user's own names."""
        for column in ("Payer Name", "Payee Name"):
            name = (row.get(column) or "").strip().lower()
            if name and any(n in name for n in self._self_names):
                return True
        return False

    def _build_txn(
        self,
        row: dict[str, Any],
        currency: str,
        account: str,
        filepath: str,
        lineno: int,
    ) -> Optional[data.Transaction]:
        """Plain CARD / TRANSFER / DEPOSIT row → two-posting transaction."""
        txn_id = row["TransferWise ID"]
        amount_dec = Decimal(row["Amount"])
        if amount_dec == 0:
            logger.warning("wise: zero-amount transaction, skipping: %s", txn_id)
            return None

        # Consistency check (decision [003]): signed Amount is the truth, the
        # Transaction Type column is a free sanity check. Warn, don't raise.
        if (amount_dec < 0) != (row["Transaction Type"] == "DEBIT"):
            logger.warning(
                "wise: sign/type mismatch for %s: Amount=%s, Type=%s",
                txn_id, amount_dec, row["Transaction Type"],
            )

        txn_date = _parse_date(row["Date"])
        description = (row.get("Description") or "").strip()

        meta: data.Meta = data.new_metadata(filepath, lineno)
        # Namespace the id per currency: the same card txn can be split across
        # two balances (e.g. CARD-3330770788 debited from both CNY and GBP),
        # so the id must not collide across currency files.
        meta["id"] = f"wise-{currency}-{txn_id}"
        meta["source"] = "wise"

        # Provenance metadata, only when populated.
        for key, column in (
            ("exchange_from", "Exchange From"),
            ("exchange_to", "Exchange To"),
            ("exchange_rate", "Exchange Rate"),
            ("exchange_to_amount", "Exchange To Amount"),
            ("card_last4", "Card Last Four Digits"),
            ("payment_reference", "Payment Reference"),
        ):
            value = (row.get(column) or "").strip()
            if value:
                meta[key] = value
        fee = (row.get("Total fees") or "").strip()
        if fee and Decimal(fee) != 0:
            meta["fee"] = fee

        # Payee: Merchant first, else Payer/Payee Name.
        payee = None
        merchant = (row.get("Merchant") or "").strip()
        if merchant:
            payee = merchant
        else:
            for column in ("Payer Name", "Payee Name"):
                name = (row.get(column) or "").strip()
                if name:
                    payee = name
                    break

        postings = [
            data.Posting(account, amount.Amount(amount_dec, currency), None, None, None, None),
        ]
        # Counterpart (decision [006]): placeholder income/expense, or
        # Equity:Transfers for self-transfers.
        if amount_dec < 0:
            counterpart = "Expenses:Uncategorized:Wise"
        else:
            counterpart = "Income:Uncategorized:Wise"
        if self._is_self_transfer(row):
            counterpart = "Equity:Transfers:Wise"
        postings.append(
            data.Posting(counterpart, amount.Amount(-amount_dec, currency), None, None, None, None)
        )

        return data.Transaction(
            meta, txn_date, "*", payee, description, frozenset({"wise"}), frozenset(), postings,
        )

    def _build_fee_txn(
        self,
        row: dict[str, Any],
        currency: str,
        account: str,
        filepath: str,
        lineno: int,
    ) -> Optional[data.Transaction]:
        """FEE-CARD row → two-posting fee transaction (decision [005])."""
        amount_dec = Decimal(row["Amount"])
        if amount_dec == 0:
            logger.warning("wise: zero-amount fee, skipping: %s", row["TransferWise ID"])
            return None

        meta: data.Meta = data.new_metadata(filepath, lineno)
        meta["id"] = f"wise-{currency}-{row['TransferWise ID']}"
        meta["source"] = "wise"

        postings = [
            data.Posting(account, amount.Amount(amount_dec, currency), None, None, None, None),
            data.Posting(
                "Expenses:BankFees:Wise", amount.Amount(-amount_dec, currency), None, None, None, None
            ),
        ]

        return data.Transaction(
            meta,
            _parse_date(row["Date"]),
            "*",
            None,
            (row.get("Description") or "").strip(),
            frozenset({"wise"}),
            frozenset(),
            postings,
        )

    def _build_cashback_txn(
        self,
        row: dict[str, Any],
        currency: str,
        account: str,
        filepath: str,
        lineno: int,
    ) -> Optional[data.Transaction]:
        """BALANCE_CASHBACK row → two-posting income transaction.

        Wise pays monthly card cashback credits (seen in BRL, 2025). Always a
        CREDIT with no counterpart, so it books deterministically to a
        dedicated income account (like fees get a dedicated expense account,
        decision [005]).
        """
        txn_id = row["TransferWise ID"]
        amount_dec = Decimal(row["Amount"])
        if amount_dec <= 0:
            logger.warning(
                "wise: BALANCE_CASHBACK row is not a credit, skipping: %s", txn_id
            )
            return None

        meta: data.Meta = data.new_metadata(filepath, lineno)
        meta["id"] = f"wise-{currency}-{txn_id}"
        meta["source"] = "wise"

        postings = [
            data.Posting(account, amount.Amount(amount_dec, currency), None, None, None, None),
            data.Posting(
                "Income:Cashback:Wise", amount.Amount(-amount_dec, currency), None, None, None, None
            ),
        ]

        return data.Transaction(
            meta,
            _parse_date(row["Date"]),
            "*",
            None,
            (row.get("Description") or "").strip(),
            frozenset({"wise"}),
            frozenset(),
            postings,
        )

    def _build_conversion(
        self,
        row: dict[str, Any],
        currency: str,
        account: str,
        filepath: str,
        lineno: int,
        rows: list[dict[str, Any]],
    ) -> list[data.Directive]:
        """BALANCE DEBIT row → merged, balanced conversion (decision [004]).

        CREDIT legs (positive amount) return [] — they are booked via the
        source-currency file under the same id.
        """
        txn_id = row["TransferWise ID"]
        description = (row.get("Description") or "").strip()
        amount_dec = Decimal(row["Amount"])
        if amount_dec >= 0:
            # Credit legs in the destination-currency file are expected and are
            # booked via the source file's DEBIT leg. A positive BALANCE row
            # carrying the source-leg fee annotation is a sign of format drift.
            if "(fee:" in description:
                logger.warning(
                    "wise: positive BALANCE row with source-leg fee annotation "
                    "(possible sign drift), skipping: %s", txn_id,
                )
            return []

        m = _CONVERT_RE.search(description)
        if not m or not re.fullmatch(r"[A-Z]{3}", m.group(4)):
            logger.warning(
                "wise: unparseable conversion description, falling back to plain txn: %s", txn_id
            )
            # Emit the plain transaction AND the fee (which the extract loop
            # would otherwise skip as consumed by this builder).
            fallback = [self._build_txn(row, currency, account, filepath, lineno)]
            fee_row = next(
                (r for r in rows if r["TransferWise ID"] == f"FEE-BALANCE-{txn_id[len('BALANCE-'):]}"),
                None,
            )
            if fee_row is not None:
                fallback.append(
                    self._build_fee_txn(fee_row, currency, account, filepath, lineno)
                )
            return [e for e in fallback if e is not None]
        desc_gross, src_ccy, dst_amount_str, dst_ccy = m.groups()
        dst_amount = _parse_br_decimal(dst_amount_str)

        # Find the matching FEE-BALANCE row (e.g. FEE-BALANCE-5232969525).
        suffix = txn_id[len("BALANCE-"):]
        fee_row = next(
            (r for r in rows if r["TransferWise ID"] == f"FEE-BALANCE-{suffix}"), None
        )

        net = abs(amount_dec)
        meta: data.Meta = data.new_metadata(filepath, lineno)
        meta["id"] = f"wise-{currency}-{txn_id}"
        meta["source"] = "wise"

        if fee_row is not None:
            fee = abs(Decimal(fee_row["Amount"]))
            gross = net + fee
            if gross != _parse_br_decimal(desc_gross):
                logger.warning(
                    "wise: conversion %s gross mismatch: net+fee=%.2f vs description %.2f %s",
                    txn_id, gross, _parse_br_decimal(desc_gross), src_ccy,
                )
            fee_m = _FEE_RE.search(description)
            if fee_m and _parse_br_decimal(fee_m.group(1)) != fee:
                logger.warning(
                    "wise: conversion %s fee mismatch: FEE row %.2f vs description %.2f",
                    txn_id, fee, _parse_br_decimal(fee_m.group(1)),
                )
            src_amount = -gross
            fee_posting = data.Posting(
                "Expenses:BankFees:Wise", amount.Amount(fee, currency), None, None, None, None
            )
        else:
            logger.warning(
                "wise: no FEE-BALANCE row for %s; booking net amount without fee", txn_id
            )
            src_amount = -net
            fee_posting = None

        postings = [
            data.Posting(account, amount.Amount(src_amount, currency), None, None, None, None),
            data.Posting(
                f"{self.account_root}:{dst_ccy}",
                amount.Amount(dst_amount, dst_ccy),
                None,
                # Total price: dst @@ net, e.g. 516.61 SGD @@ 298.98 GBP.
                amount.Amount(net / dst_amount, currency),
                None,
                None,
            ),
        ]
        if fee_posting is not None:
            postings.append(fee_posting)

        return [
            data.Transaction(
                meta,
                _parse_date(row["Date"]),
                "*",
                None,
                f"Convert {currency} to {dst_ccy}",
                frozenset({"wise"}),
                frozenset(),
                postings,
            )
        ]