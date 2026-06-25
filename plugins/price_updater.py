"""Fava extension to manually trigger BRAPI price downloads."""

from __future__ import annotations

from typing import Any

from flask import redirect, request

from fava.ext import FavaExtensionBase, extension_endpoint

from plugins.brapi_price_service import BrapiPriceUpdater


class PriceUpdaterExtension(FavaExtensionBase):
    report_title = "Price Updater"

    def __init__(self, ledger, config: str | None = None) -> None:
        super().__init__(ledger, config)
        self.last_result: dict[str, Any] | None = None

    def _service(self) -> BrapiPriceUpdater:
        cfg = self.config if isinstance(self.config, dict) else {}
        return BrapiPriceUpdater(self.ledger, cfg)

    @extension_endpoint("update_prices", ["POST"])
    def update_prices(self):
        summary = self._service().run()
        self.last_result = {
            "updated": summary.updated,
            "full_refresh": summary.full_refresh,
            "skipped": summary.skipped,
            "warnings": summary.warnings,
            "errors": summary.errors,
            "generated_files": summary.generated_files,
        }
        return redirect(request.path.rsplit("/", 1)[0] + "/")
