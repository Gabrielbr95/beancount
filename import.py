import logging
import os
import sys
import beangulp

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importers.b3 import B3Importer

# List of importers to be used by Beangulp and Fava
CONFIG = [
    B3Importer(account_root="Assets:Investment"),
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