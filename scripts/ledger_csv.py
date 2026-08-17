#!/usr/bin/env python3
"""
ledger_csv.py — Lossless round-trip between Beancount transactions and CSV.

Designed for editing transactions and their legs (account names, amounts,
metadata) in Excel, then re-importing the edited CSV back to a Beancount file.
The schema is DISCOVERED from the input file, not hardcoded: any metadata keys
present become columns, any optional posting fields used (cost, price, posting
flag) become columns.

Usage:
    python scripts/ledger_csv.py to-csv   <in.bean> <out.csv>
    python scripts/ledger_csv.py from-csv <in.csv>  <out.bean>

CSV shape: one row per transaction. Transaction-level fields come first;
postings are numbered groups of columns (`leg_1_account`, `leg_1_units_number`,
...). The number of groups is the maximum number of postings in any exported
transaction. Leave a leg's account blank to remove that leg. `txn_id` is a
synthetic unique id (1, 2, 3, ...) which must remain unique; use a fresh id
when adding a transaction.

Losslessness:
    - Semantic round-trip (account names, amounts, metadata values, tags,
      links, cost, price). Byte-exact whitespace is NOT promised — beancount's
      printer normalizes alignment.
    - Only Transaction directives are supported. Open/Close/Balance/Note/
      Price/Custom directives raise loudly (do not silently drop).
    - Meta values are stored as strings. Lossless for the typical Pluggy-style
      string metadata; lossy in TYPE for numeric/date meta (the value
      round-trips but beancount will see it as a string on reimport).
    - Internal meta keys (filename, lineno, __tolerances__, __automatic__) are
      skipped on export and synthesized on import.

Editing workflow:
    1. python scripts/ledger_csv.py to-csv tmp.bean tmp.csv
    2. Open tmp.csv in Excel. Edit the relevant `leg_N_account` column to
       reclassify (e.g. replace `Expenses:TODO` with `Expenses:Food`). Leave
       `txn_id` unique. Save as CSV (UTF-8).
    3. python scripts/ledger_csv.py from-csv tmp.csv tmp_new.bean
    4. bean-check main.bean  # verify (after swapping tmp.bean → tmp_new.bean)
"""

import argparse
import csv
import sys
from datetime import date
from decimal import Decimal, InvalidOperation

from beancount import loader
from beancount.core import amount, data
from beancount.parser import printer

# Meta keys injected by the loader; not user-authored, do not round-trip.
INTERNAL_META = frozenset({"filename", "lineno", "__tolerances__", "__automatic__"})


# ---------------------------------------------------------------------------
# Schema discovery
# ---------------------------------------------------------------------------

def discover_schema(entries):
    """Scan all entries and return a dict of discovered columns.

    Meta key ORDER is preserved as first-seen in the input file, so the
    round-trip is byte-stable on metadata ordering (beancount itself treats
    meta as a dict and does not care about order, but the file diff does).

    Raises ValueError on the first non-Transaction directive (loud failure).
    """
    txn_meta_keys: list[str] = []
    post_meta_keys: list[str] = []
    cost_types = set()
    has_price = False
    has_post_flag = False
    max_postings = 0

    def add_seen(lst, key):
        if key not in lst:
            lst.append(key)

    for entry in entries:
        if not isinstance(entry, data.Transaction):
            raise ValueError(
                f"Unsupported directive at {entry.meta.get('filename')}:"
                f"{entry.meta.get('lineno')}: {type(entry).__name__}. "
                f"Only Transaction is supported by ledger_csv.py."
            )
        for k in entry.meta:
            if k not in INTERNAL_META:
                add_seen(txn_meta_keys, k)
        for p in entry.postings:
            for k in (p.meta or {}):
                if k not in INTERNAL_META:
                    add_seen(post_meta_keys, k)
            if p.cost is not None:
                cost_types.add(type(p.cost).__name__)
            if p.price is not None:
                has_price = True
            if p.flag is not None:
                has_post_flag = True
        max_postings = max(max_postings, len(entry.postings))

    return {
        "txn_meta": txn_meta_keys,
        "post_meta": post_meta_keys,
        "cost_types": cost_types,
        "has_price": has_price,
        "has_post_flag": has_post_flag,
        # Keep one editable leg group even for an empty input file.
        "max_postings": max(1, max_postings),
    }


def build_columns(schema):
    """Stable column order. Always-present columns first, then discovered."""
    cols = ["txn_id", "date", "flag", "payee", "narration", "tags", "links"]
    cols += [f"txn_meta_{k}" for k in schema["txn_meta"]]
    for leg_idx in range(1, schema["max_postings"] + 1):
        prefix = f"leg_{leg_idx}_"
        cols += [f"{prefix}account", f"{prefix}units_number", f"{prefix}units_currency"]
        if schema["cost_types"]:
            cols += [
                f"{prefix}cost_type",
                f"{prefix}cost_number",         # Cost.number | CostSpec.number_per
                f"{prefix}cost_number_total",    # CostSpec.number_total only
                f"{prefix}cost_currency", f"{prefix}cost_label", f"{prefix}cost_date",
                f"{prefix}cost_mergeei",         # CostSpec.mergeei only
            ]
        if schema["has_price"]:
            cols += [f"{prefix}price_number", f"{prefix}price_currency"]
        if schema["has_post_flag"]:
            cols += [f"{prefix}posting_flag"]
        cols += [f"{prefix}posting_meta_{k}" for k in schema["post_meta"]]
    return cols


# ---------------------------------------------------------------------------
# Value formatting (beancount → CSV cell string)
# ---------------------------------------------------------------------------

def format_meta_value(v):
    """Render a meta value to a CSV string. Reimport stores it as a string."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, Decimal):
        return str(v)
    return str(v)


def format_cost(cost):
    """Return a dict of cost_* CSV cells from a Cost or CostSpec object."""
    cells = {"cost_type": "", "cost_number": "", "cost_number_total": "",
             "cost_currency": "", "cost_label": "", "cost_date": "", "cost_mergeei": ""}
    if cost is None:
        return cells
    if isinstance(cost, data.Cost):
        cells["cost_type"] = "Cost"
        cells["cost_number"] = str(cost.number) if cost.number is not None else ""
        cells["cost_currency"] = cost.currency or ""
        cells["cost_label"] = cost.label or ""
        cells["cost_date"] = cost.date.isoformat() if cost.date else ""
    else:  # CostSpec
        cells["cost_type"] = "CostSpec"
        cells["cost_number"] = str(cost.number_per) if cost.number_per is not None else ""
        cells["cost_number_total"] = str(cost.number_total) if cost.number_total is not None else ""
        cells["cost_currency"] = cost.currency or ""
        cells["cost_label"] = cost.label or ""
        cells["cost_date"] = cost.date.isoformat() if cost.date else ""
        cells["cost_mergeei"] = cost.mergeei or ""
    return cells


def build_row(txn, txn_id, cols, schema):
    """Build one CSV row (dict) for a transaction and all of its postings."""
    row = {c: "" for c in cols}
    row["txn_id"] = txn_id
    row["date"] = txn.date.isoformat()
    row["flag"] = txn.flag or ""
    row["payee"] = txn.payee or ""
    row["narration"] = txn.narration or ""
    row["tags"] = "|".join(sorted(txn.tags)) if txn.tags else ""
    row["links"] = "|".join(sorted(txn.links)) if txn.links else ""
    for k, v in txn.meta.items():
        if k in INTERNAL_META:
            continue
        row[f"txn_meta_{k}"] = format_meta_value(v)
    for leg_idx, posting in enumerate(txn.postings, start=1):
        prefix = f"leg_{leg_idx}_"
        row[f"{prefix}account"] = posting.account
        if posting.units is not None:
            row[f"{prefix}units_number"] = str(posting.units.number)
            row[f"{prefix}units_currency"] = posting.units.currency or ""
        if schema["cost_types"]:
            row.update({f"{prefix}{k}": v for k, v in format_cost(posting.cost).items()})
        if schema["has_price"] and posting.price is not None:
            row[f"{prefix}price_number"] = str(posting.price.number)
            row[f"{prefix}price_currency"] = posting.price.currency or ""
        if schema["has_post_flag"] and posting.flag is not None:
            row[f"{prefix}posting_flag"] = posting.flag
        for k, v in (posting.meta or {}).items():
            if k in INTERNAL_META:
                continue
            row[f"{prefix}posting_meta_{k}"] = format_meta_value(v)
    return row


# ---------------------------------------------------------------------------
# ledger → CSV
# ---------------------------------------------------------------------------

def ledger2csv(in_path, out_path):
    entries, errors, _ = loader.load_file(in_path)
    # Non-fatal load errors (e.g. "account not opened" for a standalone bean
    # file) are reported but do not block export. Fatal parse errors raise.
    if errors:
        sys.stderr.write(
            f"[warn] beancount loader reported {len(errors)} error(s) for "
            f"{in_path}; exporting transactions anyway.\n"
        )
    schema = discover_schema(entries)
    cols = build_columns(schema)

    # utf-8-sig writes a BOM so Excel opens UTF-8 correctly.
    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        txn_id = 0
        for entry in entries:
            # discover_schema already asserted all are Transactions; re-check
            # cheaply here in case of an empty file.
            if not isinstance(entry, data.Transaction):
                continue
            txn_id += 1
            writer.writerow(build_row(entry, txn_id, cols, schema))

    sys.stderr.write(
        f"[ok] {txn_id} transactions → {out_path} ({len(cols)} columns)\n"
    )


# ---------------------------------------------------------------------------
# CSV → ledger
# ---------------------------------------------------------------------------

def parse_decimal_or_none(s):
    if s is None or s == "":
        return None
    try:
        return Decimal(s)
    except InvalidOperation:
        raise ValueError(f"Cannot parse Decimal from: {s!r}")


def parse_date_or_none(s):
    if s is None or s == "":
        return None
    return date.fromisoformat(s)


def build_posting(row, prefix):
    """Reconstruct one numbered posting. Returns None if its account is empty."""
    account = row.get(f"{prefix}account", "")
    if not account:
        # Empty account = user deleted this leg in Excel. Skip.
        return None

    units = None
    num = row.get(f"{prefix}units_number", "")
    cur = row.get(f"{prefix}units_currency", "")
    if num and cur:
        units = amount.Amount(Decimal(num), cur)

    cost = None
    cost_type = row.get(f"{prefix}cost_type", "")
    if cost_type == "Cost":
        cost = data.Cost(
            parse_decimal_or_none(row.get(f"{prefix}cost_number", "")),
            row.get(f"{prefix}cost_currency", "") or None,
            row.get(f"{prefix}cost_label", "") or None,
            parse_date_or_none(row.get(f"{prefix}cost_date", "")),
        )
    elif cost_type == "CostSpec":
        cost = data.CostSpec(
            parse_decimal_or_none(row.get(f"{prefix}cost_number", "")),
            parse_decimal_or_none(row.get(f"{prefix}cost_number_total", "")),
            row.get(f"{prefix}cost_currency", "") or None,
            row.get(f"{prefix}cost_label", "") or None,
            parse_date_or_none(row.get(f"{prefix}cost_date", "")),
            row.get(f"{prefix}cost_mergeei", "") or None,
        )

    price = None
    pnum = row.get(f"{prefix}price_number", "")
    pcur = row.get(f"{prefix}price_currency", "")
    if pnum and pcur:
        price = amount.Amount(Decimal(pnum), pcur)

    flag = row.get(f"{prefix}posting_flag", "") or None

    meta = None
    for k, v in row.items():
        if k.startswith(f"{prefix}posting_meta_") and v != "":
            if meta is None:
                meta = {}
            meta[k[len(f"{prefix}posting_meta_"):]] = v

    return data.Posting(account, units, cost, price, flag, meta)


def build_txn(row, leg_count):
    """Reconstruct one data.Transaction from one CSV row and its leg columns."""
    txn_meta = data.new_metadata("<csv2ledger>", 1)
    for k, v in row.items():
        if k.startswith("txn_meta_") and v != "":
            txn_meta[k[len("txn_meta_"):]] = v

    d = parse_date_or_none(row.get("date", "")) or date.today()
    flag = row.get("flag", "") or "*"
    payee = row.get("payee", "") or None
    narration = row.get("narration", "") or ""
    tags = frozenset(t for t in (row.get("tags", "") or "").split("|") if t)
    links = frozenset(l for l in (row.get("links", "") or "").split("|") if l)

    postings = []
    for leg_idx in range(1, leg_count + 1):
        p = build_posting(row, f"leg_{leg_idx}_")
        if p is not None:
            postings.append(p)

    if not postings:
        raise ValueError(
            f"Transaction txn_id={row.get('txn_id')} has no postings "
            f"(all leg account cells empty). Restore an account or drop the row."
        )

    return data.Transaction(txn_meta, d, flag, payee, narration, tags, links, postings)


def csv2ledger(in_path, out_path):
    # utf-8-sig tolerates a BOM if Excel wrote one.
    with open(in_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not reader.fieldnames:
        raise ValueError("CSV has no header row.")
    if "posting_idx" in reader.fieldnames or "account" in reader.fieldnames:
        raise ValueError(
            "This CSV uses the old one-row-per-posting schema. "
            "Re-export the Beancount file with 'to-csv' before importing."
        )

    leg_count = 0
    for column in reader.fieldnames:
        if column.startswith("leg_") and column.endswith("_account"):
            suffix = column[len("leg_"):-len("_account")]
            if suffix.isdigit():
                leg_count = max(leg_count, int(suffix))
    if leg_count == 0:
        raise ValueError("CSV has no leg_N_account columns.")

    # Each row is a complete transaction; txn_id remains a unique, editable id.
    txn_ids = set()
    for row_number, row in enumerate(rows, start=2):
        tid = row.get("txn_id", "")
        if not tid:
            raise ValueError(f"Row {row_number} missing txn_id: {row}")
        if tid in txn_ids:
            raise ValueError(
                f"Duplicate txn_id {tid!r} on row {row_number}. "
                "Each CSV row must have a unique txn_id."
            )
        txn_ids.add(tid)

    entries = [build_txn(row, leg_count) for row in rows]

    entries.sort(key=data.entry_sortkey)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(";; -*- mode: beancount -*-\n\n")
        for e in entries:
            f.write(printer.format_entry(e))
            # format_entry already ends with \n; add one more for a single
            # blank line between entries (matches typical .bean convention).
            f.write("\n")

    sys.stderr.write(
        f"[ok] {len(entries)} transactions → {out_path}\n"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Lossless round-trip between Beancount transactions and CSV."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p2c = sub.add_parser("to-csv", help="Beancount file → CSV")
    p2c.add_argument("in_bean")
    p2c.add_argument("out_csv")

    c2p = sub.add_parser("from-csv", help="CSV → Beancount file")
    c2p.add_argument("in_csv")
    c2p.add_argument("out_bean")

    args = parser.parse_args()

    if args.command == "to-csv":
        ledger2csv(args.in_bean, args.out_csv)
    elif args.command == "from-csv":
        csv2ledger(args.in_csv, args.out_bean)


if __name__ == "__main__":
    main()
