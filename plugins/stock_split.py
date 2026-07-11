"""Plugin to adjust historical transactions for stock splits based on ledger entries.

Usage in beancount:
    option "pre_booking_plugins" "plugins.stock_split"

Inside your journal:
    2026-05-20 custom "desdobramento" "PETR4" "4"
    2026-05-20 custom "grupamento" "PETR4" "0.5"
    2026-05-20 custom "bonificacao" "PETR4" "1.05"
"""
import collections
from decimal import Decimal
from typing import Optional

from beancount.core.amount import Amount
from beancount.core.data import Custom, Entries, Transaction
from beancount.core.number import MISSING
from beancount.core.position import Cost, CostSpec

__plugins__ = ["stock_split"]

SplitError = collections.namedtuple("SplitError", "source message entry")


def stock_split(entries: Entries, _: dict, plugin_config: Optional[str] = None):
    """Adjust historical stock postings for split directives in the journal."""
    errors = []
    splits = []

    # Collect all split directives first.
    for entry in entries:
        if isinstance(entry, Custom) and entry.type in {"desdobramento", "grupamento", "bonificacao"}:
            try:
                ticker = entry.values[0].value
                ratio = Decimal(entry.values[1].value)

                if ratio == 0:
                    errors.append(SplitError(
                        source=entry.meta,
                        message=f"Ratio is 0 (sentinel — not yet enriched). Enrich this entry in corporate_actions.bean before running bean-check. Ticker: {ticker}",
                        entry=entry,
                    ))
                    continue
                if ratio < 0:
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

            if (
                posting.units is not None
                and posting.units is not MISSING
                and posting.units.number is not None
                and posting.units.number is not MISSING
            ):
                for split in splits:
                    if (
                        modified_posting.units.currency == split["ticker"]
                        and entry.date < split["date"]
                    ):
                        new_number = modified_posting.units.number * split["ratio"]

                        new_cost = modified_posting.cost
                        if new_cost is not None:
                            if isinstance(new_cost, CostSpec):
                                # Only divide when the value is an actual number.
                                # If it's None or MISSING, leave it untouched so
                                # interpolation can fill it in later.
                                replacements = {}
                                if (
                                    new_cost.number_per is not None
                                    and new_cost.number_per is not MISSING
                                ):
                                    replacements["number_per"] = (
                                        new_cost.number_per / split["ratio"]
                                    )
                                if (
                                    new_cost.number_total is not None
                                    and new_cost.number_total is not MISSING
                                ):
                                    replacements["number_total"] = (
                                        new_cost.number_total / split["ratio"]
                                    )
                                if replacements:
                                    new_cost = new_cost._replace(**replacements)
                            elif isinstance(new_cost, Cost):
                                if new_cost.number is not None:
                                    new_cost = new_cost._replace(
                                        number=new_cost.number / split["ratio"]
                                    )

                        new_price = modified_posting.price
                        if (
                            new_price is not None
                            and new_price.number is not None
                            and new_price.number is not MISSING
                        ):
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