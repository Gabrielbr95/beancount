"""Plugin to adjust historical transactions for stock splits based on ledger entries.

Usage in beancount:
    plugin "plugins.stock_split"

Inside your journal:
    2026-05-20 custom "split" "PETR4" "4"
"""
import collections
from decimal import Decimal
from typing import Optional

from beancount.core.amount import Amount
from beancount.core.data import Custom, Entries, Transaction

__plugins__ = ["stock_split"]

SplitError = collections.namedtuple("SplitError", "source message entry")


def stock_split(entries: Entries, _: dict, plugin_config: Optional[str] = None):
    """Adjust historical stock postings for split directives in the journal."""
    errors = []
    splits = []

    # Collect all split directives first.
    for entry in entries:
        if isinstance(entry, Custom) and entry.type == "split":
            try:
                ticker = entry.values[0].value
                ratio = Decimal(entry.values[1].value)

                if ratio <= 0:
                    errors.append(SplitError(
                        source=entry.meta,
                        message=f"Split ratio must be positive, got {ratio} for {ticker}",
                        entry=entry,
                    ))
                    continue

                splits.append({
                    "ticker": ticker,
                    "date": entry.date,
                    "ratio": ratio,
                })

            except (IndexError, ValueError, AttributeError) as exc:
                errors.append(SplitError(
                    source=entry.meta,
                    message=f"Erro ao processar diretiva de split em {entry.date}: {exc}",
                    entry=entry,
                ))

    # Rebuild the entry list so adjusted transactions are actually returned.
    new_entries = []
    for entry in entries:
        if not isinstance(entry, Transaction):
            new_entries.append(entry)
            continue

        new_postings = []
        for posting in entry.postings:
            modified_posting = posting

            if posting.units is not None:
                for split in splits:
                    if (
                        modified_posting.units.currency == split["ticker"]
                        and entry.date < split["date"]
                    ):
                        new_number = modified_posting.units.number * split["ratio"]

                        new_cost = modified_posting.cost
                        if new_cost is not None:
                            new_cost = new_cost._replace(
                                number=new_cost.number / split["ratio"]
                            )

                        new_price = modified_posting.price
                        if new_price is not None:
                            new_price = new_price._replace(
                                number=new_price.number / split["ratio"]
                            )

                        modified_posting = modified_posting._replace(
                            units=Amount(new_number, modified_posting.units.currency),
                            cost=new_cost,
                            price=new_price,
                        )

            new_postings.append(modified_posting)

        new_entries.append(entry._replace(postings=new_postings))

    return new_entries, errors