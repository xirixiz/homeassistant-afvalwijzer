from datetime import date
from typing import Dict, Iterable, List, Optional

from .model import WasteCollection


class WasteCollectionRepository:
    def __init__(self, items: Optional[Iterable[WasteCollection]] = None):
        self._items: List[WasteCollection] = list(items) if items else []

    def add_many(self, items: Iterable[WasteCollection]) -> None:
        self._items.extend(items)

    def sorted(self) -> List[WasteCollection]:
        return sorted(self._items, key=lambda x: (x.day, x.waste_type.lower()))

    def upcoming(self, from_day: Optional[date] = None) -> List[WasteCollection]:
        from_day = from_day or date.today()
        return [x for x in self.sorted() if x.day >= from_day]

    def on_day(self, d: date) -> List[WasteCollection]:
        return [x for x in self.sorted() if x.day == d]

    def first_upcoming_day(self, from_day: Optional[date] = None) -> Optional[date]:
        up = self.upcoming(from_day)
        return up[0].day if up else None

    def first_upcoming_type(self, from_day: Optional[date] = None) -> Optional[str]:
        first_day = self.first_upcoming_day(from_day)
        if not first_day:
            return None
        items = self.on_day(first_day)
        if not items:
            return None
        return sorted(items, key=lambda x: x.waste_type.lower())[0].waste_type

    def first_upcoming_by_type(self, from_day: Optional[date] = None) -> Dict[str, str]:
        res: Dict[str, str] = {}
        for item in self.upcoming(from_day):
            if item.waste_type not in res:
                res[item.waste_type] = item.day.isoformat()
        return res
