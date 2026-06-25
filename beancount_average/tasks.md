tier: application

## High-Level Plan
Implement the `AVERAGE` cost booking method as an independent, shippable Python package (`beancount-average`) utilizing a `.pth` hook. This package will inject our completed average-cost booking logic into the Beancount runtime in-memory, making it completely upgrade-safe and easy to distribute.

## Blockers / Open Questions
- None.

## Tasks Checklist
- [ ] Task 1: Initialize Package Repository Structure (Create `beancount_average/` source directory, `pyproject.toml`, and package metadata files)
- [ ] Task 2: Implement .pth Hook and Patching Mechanism (Write `beancount_average.pth` and `beancount_average/__init__.py` to inject the patch in memory on Python start)
- [ ] Task 3: Port and Refine Core AVERAGE Booking Logic (Implement the complete `booking_method_AVERAGE` in `beancount_average/core.py` with deterministic oldest-date sorting, correct variable mapping, and `booked_matches` population)
- [ ] Task 4: Setup Testing Runner (Create a script that activates the monkeypatch and runs Beancount's native `booking_full_test.py` suite to verify success)
- [ ] Task 5: Verify Ledger Functionality (Locally install the package in editable mode, enable AVERAGE booking in `main.bean`, and run `bean-check` to confirm zero errors)
