from typing import Any, Dict, List

from ..model import WasteCollection


class BaseCollector:
    """All collectors must use keyword-only constructors."""

    def collect(self) -> List[WasteCollection]:
        raw = self.fetch_raw()
        return self.parse(raw)

    def fetch_raw(self) -> Dict[str, Any]:
        raise NotImplementedError

    def parse(self, raw: Dict[str, Any]) -> List[WasteCollection]:
        raise NotImplementedError
