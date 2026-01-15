from datetime import date, datetime
from typing import Any

from .repository import WasteCollectionRepository


def build_ha_json(repo: WasteCollectionRepository) -> dict[str, Any]:
    today = date.today()
    tomorrow = date.fromordinal(today.toordinal() + 1)
    day_after = date.fromordinal(today.toordinal() + 2)

    first_day = repo.first_upcoming_day(today)
    first_type = repo.first_upcoming_type(today)

    first_next_date = first_day.isoformat() if first_day else None
    first_next_in_days = (first_day - today).days if first_day else None

    return {
        "today": [x.to_dict() for x in repo.on_day(today)],
        "tomorrow": [x.to_dict() for x in repo.on_day(tomorrow)],
        "day_after_tomorrow": [x.to_dict() for x in repo.on_day(day_after)],
        "first_next_date": first_next_date,
        "first_next_type": first_type,
        "first_next_in_days": first_next_in_days,
        "first_upcoming_by_type": repo.first_upcoming_by_type(today),
        "upcoming": [x.to_dict() for x in repo.upcoming(today)],
        "last_update": datetime.now().isoformat(),
    }
