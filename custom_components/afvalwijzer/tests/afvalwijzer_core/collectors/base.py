from typing import Any

from ..model import WasteCollection


class BaseCollector:
    """All collectors must use keyword-only constructors."""

    def collect(self) -> list[WasteCollection]:
        raw = self.fetch_raw()
        return self.parse(raw)

    def fetch_raw(self) -> dict[str, Any]:
        raise NotImplementedError

    def parse(self, raw: dict[str, Any]) -> list[WasteCollection]:
        raise NotImplementedError
