# Specification: Shippable AVERAGE Booking Method via .pth Hook

## Goal
Implement the `AVERAGE` cost booking method for Beancount as a standalone, shippable Python package (`beancount-average`) that dynamically hooks into Beancount on startup. This allows users to enable `AVERAGE` booking safely across different Beancount versions without modifying core Beancount source files.

## Scope
1. **Standalone Package Structure**: Establish a clean Python package structure containing `beancount_average/` logic and standard packaging configurations.
2. **Hook Mechanism**: Implement a Python `.pth` (Path Configuration) startup hook that automatically executes upon environment loading, replacing Beancount's disabled `booking_method_AVERAGE` in memory with the completed logic.
3. **Core AVERAGE Booking Logic**:
   - Complete the `booking_method_AVERAGE` logic in `beancount_average/core.py`.
   - Correctly populate `booked_matches` for both single-match and multi-match/merging code paths.
   - Resolve local variable alignment (rename `_insufficient` to `insufficient`).
   - Sort matching lots deterministically by cost date (oldest first) to resolve the merge-date selection `FIXME`.
4. **Integration Testing**: Add a script to run Beancount's native integration tests (`booking_full_test.py`) with the `beancount-average` patch active to verify 100% compliance.
5. **Distribution Config**: Define `pyproject.toml` to copy the `.pth` hook file automatically to the `site-packages` directory upon installation.

## Success Criteria
- Running Beancount's `booking_full_test.py` with `beancount-average` installed/active passes all `AVERAGE` test cases (in `_TestBookAmbiguousAVERAGE` class) successfully.
- Installing the package in a Beancount environment and running `bean-check` on a ledger using `option "booking_method" "AVERAGE"` parses and books transactions flawlessly without requiring manual library modification.
