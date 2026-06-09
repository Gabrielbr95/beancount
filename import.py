from importers.b3 import B3Importer
import beangulp

# List of importers to be used by Beangulp and Fava
CONFIG = [
    B3Importer(account_root="Assets:Investment"),
]

# Hooks to process entries after extraction (e.g., deduplication)
HOOKS = []

if __name__ == "__main__":
    ingest = beangulp.Ingest(CONFIG, HOOKS)
    ingest()