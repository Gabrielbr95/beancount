"""Pluggy API importer for Beancount.

Fetches bank account transactions from the Pluggy API (via the Meu Pluggy
proxy) and converts them to Beancount entries. Behaves like a standard
beangulp importer — trigger file pattern bridges the API source into
beangulp's file-oriented model.

Usage:
    1. Create an empty trigger file: touch export/pluggy.trigger
    2. Run: python import.py extract export/ > tmp.bean
    3. In Fava: upload a file named *.pluggy to trigger the importer
"""

from __future__ import annotations

import logging
import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional

import beangulp
import requests
from beancount.core import amount, data

logger = logging.getLogger(__name__)

PLUGGY_API_BASE = "https://api.pluggy.ai"


# ---------------------------------------------------------------------------
# API client functions
# ---------------------------------------------------------------------------

def load_credentials(path: str) -> dict[str, Any]:
    """Parse api_keys.txt for Pluggy credentials and item IDs.

    Handles the existing typo 'pluggy_cient_secret' in the file.
    Returns dict with keys: client_id, client_secret, item_ids (list[str]).
    """
    creds: dict[str, Any] = {"item_ids": []}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("http"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"')

            if key == "pluggy_client_id":
                creds["client_id"] = value
            elif key in ("pluggy_cient_secret", "pluggy_client_secret"):
                creds["client_secret"] = value
            elif key == "pluggy_item_ids":
                creds["item_ids"] = [v.strip() for v in value.split(",") if v.strip()]

    missing = []
    if "client_id" not in creds:
        missing.append("pluggy_client_id")
    if "client_secret" not in creds:
        missing.append("pluggy_client_secret (or pluggy_cient_secret)")
    if missing:
        raise ValueError(f"load_credentials: missing keys in {path}: {', '.join(missing)}")

    if not creds["item_ids"]:
        logger.warning("load_credentials: no pluggy_item_ids found in %s", path)

    return creds


def authenticate(client_id: str, client_secret: str) -> str:
    """Exchange clientId/clientSecret for an API key via POST /auth.

    Returns the API key string. Raises on non-200 with response body.
    """
    resp = requests.post(
        f"{PLUGGY_API_BASE}/auth",
        json={"clientId": client_id, "clientSecret": client_secret},
        headers={"Content-Type": "application/json"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"Pluggy auth failed (HTTP {resp.status_code}): {resp.text[:300]}"
        )
    api_key = resp.json().get("apiKey")
    if not api_key:
        raise RuntimeError(f"Pluggy auth succeeded but no apiKey in response: {resp.text[:300]}")
    logger.info("Pluggy auth OK.")
    return api_key


def fetch_accounts(api_key: str, item_id: str) -> list[dict[str, Any]]:
    """GET /accounts?itemId= — return list of account dicts for one item."""
    resp = requests.get(
        f"{PLUGGY_API_BASE}/accounts",
        params={"itemId": item_id},
        headers={"X-API-KEY": api_key},
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(
            f"fetch_accounts failed for item {item_id} (HTTP {resp.status_code}): {resp.text[:300]}"
        )
    accounts = resp.json().get("results", [])
    logger.info("fetch_accounts: item %s → %d accounts", item_id[:8], len(accounts))
    return accounts


def fetch_transactions(api_key: str, account_id: str) -> list[dict[str, Any]]:
    """GET /v2/transactions?accountId= — follow cursor pagination until exhausted.

    Returns the full list of transaction dicts for one account.
    """
    all_txns: list[dict[str, Any]] = []
    url = f"{PLUGGY_API_BASE}/v2/transactions"
    params: dict[str, str] = {"accountId": account_id}

    while True:
        resp = requests.get(url, params=params, headers={"X-API-KEY": api_key}, timeout=30)
        if resp.status_code != 200:
            raise RuntimeError(
                f"fetch_transactions failed for account {account_id} "
                f"(HTTP {resp.status_code}): {resp.text[:300]}"
            )
        body = resp.json()
        results = body.get("results", [])
        all_txns.extend(results)

        next_cursor = body.get("next")
        if not next_cursor:
            break

        # The 'next' field is a query string like "?accountId=...&after=BASE64".
        # Parse out the 'after' cursor and continue with fresh params.
        if next_cursor.startswith("?"):
            from urllib.parse import parse_qs
            parsed = parse_qs(next_cursor.lstrip("?"))
            params = {k: v[0] for k, v in parsed.items()}
        elif next_cursor.startswith("http"):
            url = next_cursor
            params = {}
        else:
            # Treat as a bare cursor value
            params = {"accountId": account_id, "after": next_cursor}

    logger.info("fetch_transactions: account %s → %d transactions", account_id[:8], len(all_txns))
    return all_txns


# ---------------------------------------------------------------------------
# Importer class
# ---------------------------------------------------------------------------

class PluggyImporter(beangulp.Importer):
    """beangulp importer that fetches transactions from the Pluggy API.

    Uses a trigger-file pattern: identify() matches files ending in '.pluggy',
    and extract() calls the Pluggy API instead of reading file content.
    """

    def __init__(
        self,
        account_map: dict[str, str],
        credentials_file: str,
        account_root: str = "Assets:Bank",
    ) -> None:
        """
        Args:
            account_map: {pluggy_account_id: beancount_account_name}
            credentials_file: path to api_keys.txt
            account_root: root account for archival (informational only)
        """
        self.account_map = account_map
        self.credentials_file = credentials_file
        self.account_root = account_root.rstrip(":")
        self._latest_date: Optional[date] = None

    @property
    def name(self) -> str:
        return "Pluggy Importer"

    def identify(self, filepath: str) -> bool:
        base = os.path.basename(filepath).lower()
        return base.endswith(".pluggy") or base == "pluggy.trigger"

    def account(self, filepath: str) -> str:
        return self.account_root

    def date(self, filepath: str) -> Optional[date]:
        return self._latest_date

    def filename(self, filepath: str) -> Optional[str]:
        d = self._latest_date or date.today()
        return f"{d:%Y-%m-%d}.pluggy.bean"

    def extract(self, filepath: str, existing: list[data.Directive]) -> list[data.Directive]:
        logger.info("Starting Pluggy import: %s", filepath)
        try:
            creds = load_credentials(self.credentials_file)
            api_key = authenticate(creds["client_id"], creds["client_secret"])
            item_ids = creds["item_ids"]

            if not item_ids:
                raise ValueError("No pluggy_item_ids configured in credentials file")

            entries: list[data.Directive] = []
            seen_txn_ids: set[str] = set()
            latest = date.min

            for item_id in item_ids:
                accounts = fetch_accounts(api_key, item_id)
                for acct in accounts:
                    acct_id = acct.get("id")
                    if not acct_id:
                        logger.warning("Account without id in item %s, skipping", item_id[:8])
                        continue

                    bc_account = self._map_account(acct_id)
                    if bc_account is None:
                        continue

                    is_credit_card = bc_account.startswith("Liabilities")
                    logger.info(
                        "Processing account: %s (%s) → %s [%s]",
                        acct.get("name", "?"), acct_id[:8], bc_account,
                        "credit" if is_credit_card else "bank",
                    )

                    txns = fetch_transactions(api_key, acct_id)
                    posted_count = 0
                    skipped_pending = 0
                    skipped_dup = 0

                    for lineno, txn in enumerate(txns, start=1):
                        if txn.get("status") != "POSTED":
                            skipped_pending += 1
                            continue

                        txn_id = txn.get("id", "")
                        if txn_id and txn_id in seen_txn_ids:
                            skipped_dup += 1
                            continue
                        if txn_id:
                            seen_txn_ids.add(txn_id)

                        entry = self._build_transaction(
                            txn, acct_id, bc_account, is_credit_card, filepath, lineno
                        )
                        if entry is not None:
                            entries.append(entry)
                            posted_count += 1
                            txn_date = entry.date
                            if txn_date > latest:
                                latest = txn_date

                    logger.info(
                        "  Account %s: %d imported, %d pending skipped, %d dup skipped",
                        acct_id[:8], posted_count, skipped_pending, skipped_dup,
                    )

            self._latest_date = latest if latest != date.min else date.today()
            entries.sort(key=data.entry_sortkey)
            logger.info("Finished Pluggy import: %d entries", len(entries))
            return entries

        except Exception:
            logger.exception("Failed Pluggy import: %s", filepath)
            raise

    # -----------------------------------------------------------------------
    # Mapping helpers
    # -----------------------------------------------------------------------

    def _map_account(self, pluggy_account_id: str) -> Optional[str]:
        """Look up Pluggy account ID in account_map. Return None with warning if missing."""
        bc_account = self.account_map.get(pluggy_account_id)
        if bc_account is None:
            logger.warning(
                "No Beancount account mapping for Pluggy account %s — skipping",
                pluggy_account_id,
            )
            return None
        return bc_account

    @staticmethod
    def _parse_date(pluggy_date_str: str) -> date:
        """Extract date from ISO string like '2026-07-10T23:59:59.000Z' → date(2026, 7, 10)."""
        return date.fromisoformat(pluggy_date_str[:10])

    @staticmethod
    def _parse_amount(value: Any) -> Decimal:
        """Convert Pluggy amount (float/int/str) to Decimal."""
        return Decimal(str(value))

    def _build_transaction(
        self,
        txn: dict[str, Any],
        pluggy_acct_id: str,
        bc_account: str,
        is_credit_card: bool,
        filepath: str,
        lineno: int,
    ) -> Optional[data.Transaction]:
        """Construct a single-leg Beancount Transaction from a Pluggy transaction dict.

        Emits only the bank/credit-card posting. The counterpart posting is
        predicted by smart_importer's PredictPostings hook (see import.py HOOKS),
        trained on existing ledger classifications (narration, payee,
        day-of-month). Pluggy category and merchant metadata are retained as
        provenance — the default PredictPostings hook does not consume custom
        metadata fields.

        Sign convention:
          - Bank accounts: Pluggy amount used as-is (negative=debit, positive=credit)
          - Credit cards:  Pluggy amount NEGATED for the CC posting (positive purchase
            → negative liability posting = more debt; negative payment → positive
            liability posting = less debt)

        Returns None if the transaction has no amount. Caller is responsible
        for filtering on status=POSTED before invoking this method.
        """
        raw_amount = txn.get("amount")
        if raw_amount is None:
            logger.warning("Transaction without amount, skipping: %s", txn.get("id"))
            return None

        amount_dec = self._parse_amount(raw_amount)
        currency = txn.get("currencyCode", "BRL")
        txn_date = self._parse_date(txn.get("date", ""))
        description = (txn.get("description") or "").strip()
        txn_id = txn.get("id", "")
        category_id = txn.get("categoryId")

        # Sign convention: credit card postings are negated (Pluggy CC perspective
        # is inverted relative to beancount liability accounts)
        acct_amount = -amount_dec if is_credit_card else amount_dec

        # Build metadata. pluggy_category_id / pluggy_category / pluggy_merchant
        # are retained as provenance — the default PredictPostings hook trains
        # on narration/payee/day-of-month only, not custom metadata.
        meta: data.Meta = data.new_metadata(filepath, lineno)
        meta["id"] = f"pluggy-{txn_id}" if txn_id else f"pluggy-{txn_date}-{lineno}"
        meta["source"] = "pluggy"
        meta["pluggy_account"] = pluggy_acct_id

        if category_id:
            meta["pluggy_category_id"] = category_id

        category = txn.get("category")
        if category:
            meta["pluggy_category"] = category

        merchant = txn.get("merchant")
        if merchant and isinstance(merchant, dict):
            merchant_name = merchant.get("name")
            if merchant_name:
                meta["pluggy_merchant"] = merchant_name

        # Payee
        payee = None
        if merchant and isinstance(merchant, dict):
            payee = merchant.get("name")

        # Single-leg posting: only the bank/credit-card side is emitted. The
        # counterpart is predicted by smart_importer's PredictPostings hook
        # (configured in import.py HOOKS), trained on existing ledger entries.
        postings = [
            data.Posting(
                bc_account,
                amount.Amount(acct_amount, currency),
                None, None, None, None,
            ),
        ]

        return data.Transaction(
            meta,
            txn_date,
            "*",
            payee,
            description,
            frozenset(),
            frozenset(),
            postings,
        )
