import logging
import os
import sys
import beangulp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importers.b3 import B3Importer
from importers.pluggy import PluggyImporter

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
    "0cdf88ca-4715-44e5-bec6-ba37a59b2ede": "Assets:Investment:Inter:Cash",
    "74a61a5f-9f8b-44ef-b519-5abff9b23226": "Liabilities:Credit:Inter:Card",
    "e4d40b2d-f720-4570-8fb6-89c9a12e1e2f": "Assets:Investment:XP:Cash",
    "ffd6004e-1066-4c1c-9ece-826c45ffda7d": "Assets:Investment:XP:Cash",
    "3d0492b4-0d84-49c0-9945-e3e9adc34d51": "Assets:Investment:BB:Savings",
    "75f30132-31a8-4b54-9be0-648009b118db": "Liabilities:Credit:BB:Card:EloGrafite",
    "25eb5f6d-2529-4377-8de5-e38160459cff": "Assets:Investment:BB:Cash",
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
]

# Hooks to process entries after extraction (e.g., deduplication)
HOOKS = []


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