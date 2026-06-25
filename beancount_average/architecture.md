# Architecture: Shippable AVERAGE Booking Method via .pth Hook

## Components

1. **`.pth` Hook (`beancount_average.pth`)**:
   - Placed in `site-packages` during package installation.
   - Executes a single, zero-dependency bootstrap line on Python interpreter startup: `import beancount_average; beancount_average.patch()`.

2. **Patch Dispatcher (`beancount_average/__init__.py`)**:
   - Defines the `patch()` function.
   - Imports `beancount.parser.booking_method` and replaces `booking_method_AVERAGE` with our completed implementation.
   - Dynamically updates the `_BOOKING_METHODS` mapping dictionary to point `Booking.AVERAGE` to the completed function.

3. **Core AVERAGE Booking Logic (`beancount_average/core.py`)**:
   - Contains the production-grade implementation of `booking_method_AVERAGE`.
   - Leverages Beancount core types (`Amount`, `Cost`, `Inventory`, `flags.FLAG_MERGING`, and `ZERO`).
   - Implements deterministic oldest-first date selection when merging multiple lots using `datetime.date.min` as a fallback.
   - Populates `booked_matches` correctly for proper inventory accounting and downstream tracking.

4. **Installer Config (`pyproject.toml`)**:
   - Standard PyPA configuration for a Python package.
   - Configures `setuptools` to install the package and copies `beancount_average.pth` directly into the environment's `site-packages` folder.

## Data Flow & Processing

On Python startup (e.g. running `bean-check` or starting `fava`):
1. The Python interpreter scans `site-packages` and executes the code inside `beancount_average.pth`.
2. `beancount_average.patch()` executes, importing Beancount's `booking_method` module and replacing `booking_method_AVERAGE` in `sys.modules` with the finished logic.
3. Beancount loads the ledger file and runs `booking.book()`.
4. When `booking.book()` encounters a reducing posting under `option "booking_method" "AVERAGE"`, it dispatches to the patched `booking_method_AVERAGE` function.
5. Our custom logic resolves the reductions, outputs any necessary merging entries, populates `booked_matches`, and returns the results to the Beancount parser.

## Key Choices & Tradeoffs

- **No disk modifications**: By patching `beancount` in memory at startup, we bypass the need to touch any files in the Beancount virtual environment on disk.
- **Upstream upgrade safety**: When the user upgrades Beancount via pip, the custom patcher package remains installed in `site-packages` and automatically patches the new version of Beancount next time it runs.
- **Test execution**: To run the Beancount test suite, our testing script programmatically imports `beancount_average` to patch the environment and then invokes Beancount's unittest runner.
