import logging
import os
import sys
import beangulp
# Smart Importer is disabled: the combined Pluggy bank/card importer can
# generate invalid multi-auto-posting transactions. See task 29.
# from smart_importer import PredictPostings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importers.b3 import B3Importer
from importers.pluggy import PluggyImporter
from importers.ibkr import Importer as IBKRImporter
from importers.wise import WiseImporter

# Pluggy account mapping: {pluggy_account_id: beancount_account}
# Item 1 — Banco Inter
#   0cdf88ca = Conta Corrente → existing Inter:Cash
#   74a61a5f = Credit card → new Inter:Card
# Item 2 — XP (both checking accounts map to same account; dedup by txn id)
#   e4d40b2d = XP checking #1
#   ffd6004e = XP checking #2
# Item 3 — Banco do Brasil
#   3d0492b4 = Savings → existing BB:Savings
#   75f30132 = OUROCARD ELO GRAFITE → new, separate
#   25eb5f6d = Checking → existing BB:Cash
#   987decad = OUROCARD PLATINUM VISA → new, separate
PLUGGY_ACCOUNT_MAP = {
    "0cdf88ca-4715-44e5-bec6-ba37a59b2ede": "Assets:Bank:Inter:Cash",
    "74a61a5f-9f8b-44ef-b519-5abff9b23226": "Liabilities:Credit:Inter:Card",
    "e4d40b2d-f720-4570-8fb6-89c9a12e1e2f": "Assets:Bank:XP:Cash",
    "ffd6004e-1066-4c1c-9ece-826c45ffda7d": "Assets:Bank:XP:Cash",
    "3d0492b4-0d84-49c0-9945-e3e9adc34d51": "Assets:Bank:BB:Savings",
    "75f30132-31a8-4b54-9be0-648009b118db": "Liabilities:Credit:BB:Card:EloGrafite",
    "25eb5f6d-2529-4377-8de5-e38160459cff": "Assets:Bank:BB:Cash",
    "987decad-afee-4c0e-950e-85c3006a4b2e": "Liabilities:Credit:BB:Card:PlatinumVisa",
}


# List of importers to be used by Beangulp and Fava
CONFIG = [
    B3Importer(account_root="Assets:Investment"),
    PluggyImporter(
        account_map=PLUGGY_ACCOUNT_MAP,
        credentials_file=os.path.join(os.path.dirname(os.path.abspath(__file__)), "api_keys.txt"),
        account_root="Assets:Bank",
    ),
    # IBKR Flex Query XML importer (vendored from uabean, decision [005]).
    # Account names use the ledger's singular "Investment" convention; see
    # plan/decisions_ibkr.md decision [002].
    IBKRImporter(
        cash_account="Assets:Bank:IBKR:Cash:{currency}",
        assets_account="Assets:Investment:IBKR:{symbol}",
        div_account="Income:Investment:IBKR:{symbol}:Dividend",
        interest_account="Income:Investment:IBKR:Interest",
        wht_account="Expenses:Investment:IBKR:WithholdingTax",
        fees_account="Expenses:Investment:IBKR:Fees",
        pnl_account="Income:Investment:IBKR:{symbol}:PnL",
        document_archiving_account="ibkr",
    ),
    # Wise per-currency statement CSVs (plan/tasks_wise.md). emit_balance=True
    # (decision [007], amended): the user downloaded the full history
    # (2022-05-13 → 2026-08-18, 5 windows in export/), the 2022 window starts
    # from zero (account creation), so the history itself anchors every Wise
    # account. Windows must be extracted/processed in chronological order.
    WiseImporter(emit_balance=True),
]

# Hooks to process entries after extraction.
# PredictPostings trains on existing ledger entries and predicts the missing
# counterpart posting for single-leg Pluggy transactions. Order matters: B3
# runs before Pluggy in CONFIG, so B3 entries are in existing_entries when
# Pluggy's dedup runs, and both feed the training set for PredictPostings.
#
# TODO: existing tmp.bean Pluggy entries still carry two-leg
# Expenses:TODO / Income:TODO counterparts. PredictPostings will learn to
# predict TODO accounts until those are manually reclassified. See
# activeContext.md and Decision [018].
HOOKS = [
    # PredictPostings().hook,
]


def configure_logging() -> None:
    os.makedirs("logs", exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")

    file_handler = logging.FileHandler(os.path.join("logs", "importer.log"), encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)


if __name__ == "__main__":
    # Windows defaults stdout to cp1252 when redirected. Force UTF-8 so the
    # output bean file is valid for beancount and Fava.
    sys.stdout.reconfigure(encoding="utf-8")
    configure_logging()
    ingest = beangulp.Ingest(CONFIG, HOOKS)
    ingest()
