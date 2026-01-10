from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict


@dataclass(frozen=True, slots=True)
class WasteCollection:
    day: date
    waste_type: str

    @staticmethod
    def from_any(day_value: Any, waste_type: str) -> "WasteCollection":
        if isinstance(day_value, datetime):
            d = day_value.date()
        elif isinstance(day_value, date):
            d = day_value
        elif isinstance(day_value, str):
            d = datetime.strptime(day_value, "%Y-%m-%d").date()
        else:
            raise TypeError(
                f"day_value must be date, datetime, or str, got {type(day_value)}"
            )
        return WasteCollection(day=d, waste_type=waste_type)

    def to_dict(self) -> Dict[str, str]:
        return {"type": self.waste_type, "date": self.day.isoformat()}
