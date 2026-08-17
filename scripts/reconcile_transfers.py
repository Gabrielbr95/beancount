#!/usr/bin/env python3
"""Report exact-match candidates in the Equity:Transfers clearing accounts.

This first version is read-only. It intentionally excludes broker investment
settlements because one bank transfer can fund several trades and fees.

Usage:
    python scripts/reconcile_transfers.py main.bean
"""

import argparse
import hashlib
import os
import re
import sys
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path
from tempfile import NamedTemporaryFile

from beancount import loader
from beancount.core import data


TRANSFER_ACCOUNT = "Equity:Transfers"
INVESTMENT_TRANSFER_ACCOUNT = "Equity:Transfers:Investments"
MAX_DELAY_DAYS = 4
AUTO_LINK_PREFIX = "auto-transfer-"
AUTO_LINK_PATTERN = re.compile(r"\s+\^auto-transfer-[A-Za-z0-9-]+")


@dataclass(frozen=True)
class TransferPosting:
    """One numeric posting eligible for cash-transfer reconciliation."""

    transaction_date: date
    narration: str
    account: str
    number: Decimal
    currency: str
    filename: str
    lineno: int


@dataclass(frozen=True)
class Reconciliation:
    """Exact-match transfer reconciliation results."""

    unique_pairs: list[tuple[TransferPosting, TransferPosting]]
    missing: list[TransferPosting]
    ambiguous: list[tuple[TransferPosting, list[TransferPosting]]]


def is_eligible_account(account: str) -> bool:
    """Return whether account is a non-investment Equity:Transfers account."""
    return (
        account == TRANSFER_ACCOUNT
        or (
            account.startswith(f"{TRANSFER_ACCOUNT}:")
            and not account.startswith(f"{INVESTMENT_TRANSFER_ACCOUNT}:")
            and account != INVESTMENT_TRANSFER_ACCOUNT
        )
    )


def collect_transfer_postings(entries, include_linked=False):
    """Return all eligible numeric transfer postings from Transaction entries.

    A non-numeric clearing-account posting cannot be matched by this report, so
    it raises instead of silently disappearing from the result.
    """
    postings = []
    for entry in entries:
        if not isinstance(entry, data.Transaction):
            continue
        if entry.links and not include_linked:
            continue
        for posting in entry.postings:
            if not is_eligible_account(posting.account):
                continue
            if posting.units is None:
                raise ValueError(
                    f"Cannot reconcile amount-less posting at "
                    f"{entry.meta.get('filename')}:{entry.meta.get('lineno')} "
                    f"in {posting.account}."
                )
            postings.append(
                TransferPosting(
                    transaction_date=entry.date,
                    narration=entry.narration,
                    account=posting.account,
                    number=posting.units.number,
                    currency=posting.units.currency,
                    filename=entry.meta.get("filename", "<unknown>"),
                    lineno=entry.meta.get("lineno", 0),
                )
            )
    return postings


def is_eligible_transaction(entry):
    """Return whether a transaction has a non-investment transfer posting."""
    return isinstance(entry, data.Transaction) and any(
        is_eligible_account(posting.account) for posting in entry.postings
    )


def is_candidate(first: TransferPosting, second: TransferPosting) -> bool:
    """Return whether two postings meet the exact cash-transfer rules."""
    return (
        first.account == second.account
        and first.currency == second.currency
        and first.number != 0
        and first.number == -second.number
        and abs((first.transaction_date - second.transaction_date).days)
        <= MAX_DELAY_DAYS
    )


def posting_sort_key(posting: TransferPosting):
    """Keep report output stable and chronological."""
    return (posting.transaction_date, posting.filename, posting.lineno, posting.account)


def best_group_pairs(negative_indexes, positive_indexes, postings):
    """Maximize exact matches, then minimize delay, within one value group.

    The lists are chronological. The dynamic program considers only noncrossing
    pairings, which is sufficient for date-distance matching: crossed pairs can
    always be uncrossed without increasing either delay.
    """
    negative_indexes = sorted(
        negative_indexes, key=lambda index: posting_sort_key(postings[index])
    )
    positive_indexes = sorted(
        positive_indexes, key=lambda index: posting_sort_key(postings[index])
    )

    @cache
    def best(negative_count, positive_count):
        if negative_count == 0 or positive_count == 0:
            return (0, 0, ())

        options = [
            best(negative_count - 1, positive_count),
            best(negative_count, positive_count - 1),
        ]
        negative_index = negative_indexes[negative_count - 1]
        positive_index = positive_indexes[positive_count - 1]
        negative = postings[negative_index]
        positive = postings[positive_index]
        if is_candidate(negative, positive):
            matched_count, total_delay, pairs = best(
                negative_count - 1, positive_count - 1
            )
            delay = abs((negative.transaction_date - positive.transaction_date).days)
            options.insert(
                0,
                (matched_count + 1, total_delay + delay, pairs + ((negative_index, positive_index),)),
            )

        return max(options, key=lambda option: (option[0], -option[1]))

    return best(len(negative_indexes), len(positive_indexes))[2]


def reconcile(postings: list[TransferPosting]) -> Reconciliation:
    """Pair interchangeable exact values and report unmatched leftovers."""
    groups = {}
    for index, posting in enumerate(postings):
        key = (posting.account, posting.currency, abs(posting.number))
        groups.setdefault(key, {"negative": [], "positive": []})
        if posting.number < 0:
            groups[key]["negative"].append(index)
        elif posting.number > 0:
            groups[key]["positive"].append(index)

    unique_pairs = []
    matched_indexes = set()
    for group in groups.values():
        for negative_index, positive_index in best_group_pairs(
            group["negative"], group["positive"], postings
        ):
            unique_pairs.append((postings[negative_index], postings[positive_index]))
            matched_indexes.update((negative_index, positive_index))

    missing = [
        posting for index, posting in enumerate(postings) if index not in matched_indexes
    ]
    return Reconciliation(unique_pairs, missing, [])


def format_posting(posting: TransferPosting) -> str:
    """Render enough context to locate a posting for manual review."""
    narration = posting.narration or "<no narration>"
    return (
        f"{posting.transaction_date} | {posting.number} {posting.currency} | "
        f"{posting.account} | {narration!r} | {posting.filename}:{posting.lineno}"
    )


def render_report(results: Reconciliation) -> str:
    """Render a read-only transfer reconciliation report."""
    lines = [
        "Exact Transfer Reconciliation (read-only)",
        (
            "Rules: same transfer account/currency, equal-and-opposite amount, maximum "
            f"{MAX_DELAY_DAYS}-calendar-day delay."
        ),
        "Scope: Equity:Transfers excluding Equity:Transfers:Investments.",
        "",
        f"EXACT MATCHES ({len(results.unique_pairs)})",
        "-" * 72,
    ]
    for first, second in sorted(
        results.unique_pairs, key=lambda pair: posting_sort_key(pair[0])
    ):
        delay_days = abs((first.transaction_date - second.transaction_date).days)
        lines.extend(
            [
                f"{format_posting(first)}",
                f"  <-> {format_posting(second)}",
                f"  delay: {delay_days} day(s)",
            ]
        )
    if not results.unique_pairs:
        lines.append("None.")

    lines.extend(["", f"MISSING COUNTERPARTS ({len(results.missing)})", "-" * 72])
    lines.extend(format_posting(posting) for posting in sorted(results.missing, key=posting_sort_key))
    if not results.missing:
        lines.append("None.")

    lines.extend(["", f"AMBIGUOUS CANDIDATES ({len(results.ambiguous)})", "-" * 72])
    for posting, candidates in sorted(
        results.ambiguous, key=lambda item: posting_sort_key(item[0])
    ):
        lines.append(format_posting(posting))
        for candidate in sorted(candidates, key=posting_sort_key):
            lines.append(f"  ? {format_posting(candidate)}")
    if not results.ambiguous:
        lines.append("None.")

    return "\n".join(lines) + "\n"


def link_for_pair(first: TransferPosting, second: TransferPosting) -> str:
    """Create a stable link name from the two source transaction locations."""
    locations = sorted(
        (f"{posting.filename}:{posting.lineno}" for posting in (first, second))
    )
    digest = hashlib.sha256("|".join(locations).encode()).hexdigest()[:10]
    pair_date = min(first.transaction_date, second.transaction_date)
    return f"{AUTO_LINK_PREFIX}{pair_date:%Y%m%d}-{digest}"


def build_link_changes(entries, pairs, rewrite):
    """Return source-file header edits as {(path, line): {links}}.

    In rewrite mode every eligible transaction first loses this script's
    existing links. Other user-authored links are untouched.
    """
    changes = {}
    if rewrite:
        for entry in entries:
            if not is_eligible_transaction(entry):
                continue
            if any(link.startswith(AUTO_LINK_PREFIX) for link in entry.links):
                changes.setdefault((entry.meta["filename"], entry.meta["lineno"]), set())

    for first, second in pairs:
        link = link_for_pair(first, second)
        for posting in (first, second):
            changes.setdefault((posting.filename, posting.lineno), set()).add(link)
    return changes


def rewrite_header(line, links):
    """Replace auto-transfer links on one transaction header and preserve all else."""
    newline = "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
    body = line[: -len(newline)] if newline else line
    body = AUTO_LINK_PATTERN.sub("", body)
    return body + "".join(f" ^{link}" for link in sorted(links)) + newline


def apply_link_changes(changes):
    """Atomically write planned header changes and return changed source paths."""
    changes_by_file = {}
    for (filename, lineno), links in changes.items():
        changes_by_file.setdefault(Path(filename), {})[lineno] = links

    changed_paths = []
    for path, file_changes in changes_by_file.items():
        with path.open(encoding="utf-8", newline="") as source:
            lines = source.readlines()
        for lineno, links in file_changes.items():
            if not 1 <= lineno <= len(lines):
                raise ValueError(f"Cannot update {path}:{lineno}: line does not exist.")
            lines[lineno - 1] = rewrite_header(lines[lineno - 1], links)

        with NamedTemporaryFile(
            "w", encoding="utf-8", newline="", dir=path.parent, delete=False
        ) as temporary:
            temporary.writelines(lines)
            temporary_path = Path(temporary.name)
        os.replace(temporary_path, path)
        changed_paths.append(path)
    return changed_paths


def main():
    parser = argparse.ArgumentParser(
        description="Report exact-match candidates in Equity:Transfers."
    )
    parser.add_argument("ledger", help="Top-level Beancount ledger, e.g. main.bean")
    parser.add_argument(
        "--apply", action="store_true", help="Write links for exact matches."
    )
    parser.add_argument(
        "--rewrite",
        action="store_true",
        help="Rebuild this script's links across all eligible transactions (requires --apply).",
    )
    args = parser.parse_args()
    if args.rewrite and not args.apply:
        parser.error("--rewrite requires --apply.")

    entries, errors, _ = loader.load_file(args.ledger)
    if errors:
        sys.stderr.write(
            f"[warn] Beancount reported {len(errors)} error(s) while loading "
            f"{args.ledger}; reporting the transactions it could load.\n"
        )

    postings = collect_transfer_postings(entries, include_linked=args.rewrite)
    results = reconcile(postings)
    sys.stdout.write(render_report(results))

    if args.apply:
        changes = build_link_changes(entries, results.unique_pairs, args.rewrite)
        changed_paths = apply_link_changes(changes)
        sys.stdout.write(
            f"[ok] Applied {len(results.unique_pairs)} auto-transfer link(s) to "
            f"{len(changes)} transaction(s) in {len(changed_paths)} file(s).\n"
        )


if __name__ == "__main__":
    main()
