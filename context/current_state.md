# Current State: B3 Importer + Fava Setup

## What has already been done

- Built a **minimal B3 XLSX importer** in `importers/b3.py`.
- Kept file recognition **by filename only** (`movimentacao` / `negociacao`).
- Verified the importer on the sample files:
  - `export_samples/negociacao-sample.xlsx` -> 2 entries
  - `export_samples/movimentacao-sample.xlsx` -> 21 entries
- Added logging setup in `import.py`.
- Logs now write to `logs/importer.log`.
- The importer still prints to console.

## Important user preferences

- Keep the importer **simple**.
- Do **not** over-engineer or anticipate edge cases.
- Keep **recognition by filename only** for now.
- When parsing fails, **raise errors** and keep a **comprehensive log**.

## Current code status

### `importers/b3.py`

- Minimal importer implementation.
- Uses account style:
  - `Assets:Investment:<Broker>:<Ticker>`
  - `Assets:Investment:<Broker>:Cash`
- Handles the sample B3 movimentação and negociação layouts.
- Uses row-level logging.
- Ignores `DIREITOS DE SUBSCRICAO - EXERCIDO` in movimentações.

### `import.py`

- Configures logging with:
  - `logs/importer.log`
  - console output
- Automatically creates the `logs/` folder.

## Fava issue discussed

The user asked why the B3 importer may not appear in Fava.

Likely causes discussed:

1. Fava must be configured with:
   - `import-config` pointing to this repo’s `import.py`
   - `import-dirs` pointing to the folder with the XLSX files
2. The current `identify()` logic is filename-based, so files must contain:
   - `movimentacao`
   - or `negociacao`

The user explicitly wants to keep filename recognition only for now.

## Next requested work

- Help configure `main.beancount` for Fava.
- Likely need to add / verify Fava-related options or document the exact setup.

## Recent update

- Added a new ignore directive for `DIREITOS DE SUBSCRICAO - EXERCIDO`.
- The importer now skips this movement type instead of treating it as a zero-cost share receipt.
