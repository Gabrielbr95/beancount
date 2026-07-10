#!/usr/bin/env python3
"""
reconcile_actions.py — Route, enrich and sanity-check B3 beancount extract output.

Usage:
    python reconcile_actions.py tmp.bean
    python reconcile_actions.py tmp.bean --rewrite
"""

import argparse
import re
import sys
from datetime import date, timedelta
from pathlib import Path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description="Route, enrich and sanity-check B3 beancount extract output."
    )
    parser.add_argument(
        "tmp_bean",
        help="Path to the beangulp extract output file (e.g. tmp.bean)",
    )
    parser.add_argument(
        "--rewrite",
        action="store_true",
        default=False,
        help="Full rewrite of output files instead of append (default: append, dedup by id)",
    )
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

CORPORATE_TYPES = {"bonificacao", "desdobramento", "grupamento"}
INCOME_CUSTOM_TYPES = {"dividendo", "jcp", "rendimento"}
INCOME_NARRATION_KEYWORDS = re.compile(
    r"dividend|jcp|interest|rendimento|dividendo", re.IGNORECASE
)

# Regex for the first directive line of a block
_DATE_PREFIX = re.compile(r"^\d{4}-\d{2}-\d{2}\s+")
_CUSTOM_TYPE = re.compile(r'custom\s+"(\w+)"')
_TXN_LINE = re.compile(r'(?:txn|\*)\s+"')


def _classify_block(lines):
    """Return one of 'transactions', 'income', 'corporate_actions'."""
    # Find first non-blank line
    directive_line = ""
    for ln in lines:
        stripped = ln.strip()
        if stripped:
            directive_line = stripped
            break

    if not _DATE_PREFIX.match(directive_line):
        return "transactions"  # comments, includes, etc.

    custom_m = _CUSTOM_TYPE.search(directive_line)
    if custom_m:
        ctype = custom_m.group(1).lower()
        if ctype in CORPORATE_TYPES:
            return "corporate_actions"
        if ctype in INCOME_CUSTOM_TYPES:
            return "income"

    # txn / * entries
    if _TXN_LINE.search(directive_line) or (' * "' in directive_line) or (' txn "' in directive_line):
        if INCOME_NARRATION_KEYWORDS.search(directive_line):
            return "income"

    return "transactions"


# ---------------------------------------------------------------------------
# Task 8: parse_tmp_bean
# ---------------------------------------------------------------------------

def parse_tmp_bean(path):
    """
    Read tmp.bean, split into entry blocks, classify each.
    Returns dict: {transactions: [...], income: [...], corporate_actions: [...]}.
    Each item is the raw block text (joined lines).
    """
    text = Path(path).read_text(encoding="utf-8")

    # Split on two-or-more blank lines
    raw_blocks = re.split(r"\n{2,}", text)

    buckets = {"transactions": [], "income": [], "corporate_actions": []}

    for raw in raw_blocks:
        lines = raw.splitlines()
        # Keep only blocks that have at least one substantive line
        substantive = [ln for ln in lines if ln.strip()]
        if not substantive:
            continue

        # Skip blocks that are purely comment/blank headers with no date line
        has_date_line = any(_DATE_PREFIX.match(ln.strip()) for ln in substantive)
        if not has_date_line:
            continue

        category = _classify_block(substantive)
        buckets[category].append(raw.strip())

    return buckets


# ---------------------------------------------------------------------------
# Task 9: load_events_bean
# ---------------------------------------------------------------------------

# Strip tags (^yahoo, ^brapi, etc.) before matching the event regex
_TAG_SUFFIX_RE = re.compile(r"\s+\^\S+(\s+\^\S+)*\s*$")
# Ratio may be quoted ("4") in legacy Yahoo events or bare (4) after the
# beancount-syntax fix. Accept either.
_EVENT_RE = re.compile(
    r'^(\d{4}-\d{2}-\d{2})\s+custom\s+"(\w+)"\s+"([^"]+)"\s+"?([^"\s]+)"?'
)

CORPORATE_ACTION_TYPES = {"desdobramento", "grupamento", "bonificacao"}


def load_events_bean(prices_dir):
    """
    Scan all *_events.bean files in prices_dir.
    Return list of dicts: {ticker, type, date, ratio, raw}.
    Tag-agnostic: strips ^yahoo / ^brapi suffixes before parsing.
    Only loads split-type events (desdobramento/grupamento/bonificacao).
    """
    prices_path = Path(prices_dir)
    events = []

    if not prices_path.exists():
        return events

    for event_file in prices_path.glob("*_events.bean"):
        for line in event_file.read_text(encoding="utf-8").splitlines():
            # Strip tag suffixes before matching
            clean = _TAG_SUFFIX_RE.sub("", line.strip())
            m = _EVENT_RE.match(clean)
            if not m:
                continue
            etype = m.group(2).lower()
            # Only load corporate action types — ignore dividendo/jcp/rendimento
            if etype not in CORPORATE_ACTION_TYPES:
                continue
            event_date = date.fromisoformat(m.group(1))
            events.append({
                "ticker": m.group(3),
                "type": etype,
                "date": event_date,
                "ratio": m.group(4),
                "raw": line,
            })

    return events


# ---------------------------------------------------------------------------
# Task 10: enrich_corporate_actions
# ---------------------------------------------------------------------------

_CORP_DIRECTIVE_RE = re.compile(
    # Ratio may be quoted ("0") in Yahoo events or unquoted (0) in B3 extract.
    r'^(\d{4}-\d{2}-\d{2})\s+custom\s+"(\w+)"\s+"([^"]+)"\s+"?([^"\s]+)"?'
)
_DATE_WINDOW = 5  # days


def _find_event(ticker, ctype, entry_date, events):
    """Return best matching event or None (within ±5 days, same ticker & type)."""
    best = None
    best_drift = None
    for ev in events:
        if ev["ticker"] != ticker or ev["type"] != ctype.lower():
            continue
        drift = abs((ev["date"] - entry_date).days)
        if drift <= _DATE_WINDOW:
            if best_drift is None or drift < best_drift:
                best = ev
                best_drift = drift
    return best


def enrich_corporate_actions(corp_blocks, events):
    """
    Enrich corporate action blocks with BRAPI ratio data.
    Returns (enriched_blocks, warnings).
    """
    enriched = []
    warnings = []

    for block in corp_blocks:
        lines = block.splitlines()
        # Find directive line (first non-blank)
        dir_idx = next(
            (i for i, ln in enumerate(lines) if ln.strip() and _DATE_PREFIX.match(ln.strip())),
            None,
        )
        if dir_idx is None:
            enriched.append(block)
            continue

        directive = lines[dir_idx]
        m = _CORP_DIRECTIVE_RE.match(directive)
        if not m:
            enriched.append(block)
            continue

        entry_date = date.fromisoformat(m.group(1))
        ctype = m.group(2).lower()
        ticker = m.group(3)
        current_ratio = m.group(4)

        ev = _find_event(ticker, ctype, entry_date, events)

        prefix_comments = []

        if ev is None:
            prefix_comments.append("; ⚠ no Yahoo match — ratio unknown")
            warnings.append(f"{ticker} {ctype} {entry_date}: no Yahoo match — ratio unknown")
        else:
            drift = abs((ev["date"] - entry_date).days)
            if drift > 1:
                prefix_comments.append(
                    f"; ⚠ date drift {drift} days vs Yahoo {ev['date']}"
                )
                warnings.append(
                    f"{ticker} {ctype} {entry_date}: date drift {drift} days vs Yahoo {ev['date']}"
                )

            # Replace ratio "0" sentinel with Yahoo value, bare (per beancount
            # custom-directive syntax: numbers are unquoted).
            if current_ratio == "0" and ev["ratio"] != "0":
                directive = (
                    directive[: m.start(4)]
                    + ev["ratio"]
                    + directive[m.end(4):]
                )

            # Mark enrichment via beancount-valid metadata. NOTE: `^link` tags
            # are NOT valid grammar on custom directives (bean-check rejects
            # them as "unexpected LINK"), so we use a metadata key instead.
            if not any(ln.strip().startswith("yahoo-enriched:") for ln in lines):
                # Insert metadata right after the directive line.
                lines.insert(dir_idx + 1, '  yahoo-enriched: TRUE')

        lines[dir_idx] = directive

        new_block_lines = prefix_comments + lines
        enriched.append("\n".join(new_block_lines))

    return enriched, warnings


# ---------------------------------------------------------------------------
# Income sanity-check intentionally removed.
# Yahoo Finance cannot distinguish JCP from dividendo (no label field).
# B3 is ground truth for income amounts — no external comparison needed.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Task 12: append_to_file
# ---------------------------------------------------------------------------

_ID_RE = re.compile(r'\bid:\s+"([^"]+)"')


def _extract_id(block):
    """Return the id metadata value from a block, or None."""
    m = _ID_RE.search(block)
    return m.group(1) if m else None


def append_to_file(path, blocks, rewrite=False):
    """
    Write blocks to path.
    rewrite=True: full overwrite.
    rewrite=False: read existing, skip blocks whose id already exists, append new.
    """
    path = Path(path)

    if rewrite:
        content = "\n\n".join(blocks)
        path.write_text(content + "\n" if content else "", encoding="utf-8")
        return

    # Append / dedup mode
    existing_ids = set()
    if path.exists():
        existing_text = path.read_text(encoding="utf-8")
        for m in _ID_RE.finditer(existing_text):
            existing_ids.add(m.group(1))
    else:
        existing_text = ""

    new_blocks = []
    for block in blocks:
        bid = _extract_id(block)
        if bid and bid in existing_ids:
            continue  # duplicate
        new_blocks.append(block)
        if bid:
            existing_ids.add(bid)

    if not new_blocks:
        return

    with path.open("a", encoding="utf-8") as f:
        # Ensure file ends with newline before appending
        if existing_text and not existing_text.endswith("\n"):
            f.write("\n")
        if existing_text.strip():
            f.write("\n")
        f.write("\n\n".join(new_blocks))
        f.write("\n")


# ---------------------------------------------------------------------------
# Task 13: main wire-up
# ---------------------------------------------------------------------------

def main():
    args = parse_args()
    tmp_bean = Path(args.tmp_bean)
    if not tmp_bean.exists():
        sys.exit(
            f"ERROR: {tmp_bean} does not exist. "
            f"Run: python import.py extract export\\ > tmp.bean"
        )

    base_dir = tmp_bean.parent
    prices_dir = base_dir / "prices"

    buckets = parse_tmp_bean(tmp_bean)
    events = load_events_bean(prices_dir)

    enriched_corp, corp_warnings = enrich_corporate_actions(
        buckets["corporate_actions"], events
    )

    rewrite = args.rewrite
    append_to_file(base_dir / "corporate_actions.bean", enriched_corp, rewrite)
    append_to_file(base_dir / "income_events.bean", buckets["income"], rewrite)
    append_to_file(base_dir / "transactions.bean", buckets["transactions"], rewrite)

    # Print discrepancy report
    all_warnings = corp_warnings
    if all_warnings:
        print("\n=== DISCREPANCY REPORT ===")
        for w in all_warnings:
            print(f"  {w}")
        print(f"  Total: {len(all_warnings)} warning(s)")
    else:
        print("Reconcile complete. No discrepancies found.")

    print(f"\nWrote:")
    print(f"  corporate_actions.bean  ({len(enriched_corp)} entries)")
    print(f"  income_events.bean      ({len(buckets['income'])} entries)")
    print(f"  transactions.bean       ({len(buckets['transactions'])} entries)")


if __name__ == "__main__":
    main()
