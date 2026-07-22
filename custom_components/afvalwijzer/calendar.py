"""Calendar entity for Afvalwijzer."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import dt as dt_util

from .const.const import CONF_COLLECTOR, CONF_EXCLUDE_LIST, DOMAIN

_LOGGER = logging.getLogger(__name__)


def _to_date(value) -> date | None:
    """Coerce a waste data value (str, datetime or date) into a date.

    Cached coordinator data stores datetimes as ISO strings (e.g.
    "2026-07-22T00:00:00"), so plain dates and full timestamps must
    both be accepted.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        parsed_dt = dt_util.parse_datetime(value)
        if parsed_dt is not None:
            return parsed_dt.date()
        return dt_util.parse_date(value)
    return None


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Afvalwijzer calendar."""
    entry_id = getattr(config_entry, "entry_id", "test_entry_id")
    coordinator = hass.data.get(DOMAIN, {}).get(entry_id, {}).get("coordinator")

    if coordinator:
        async_add_entities([AfvalwijzerCalendar(coordinator, entry_id)])
    else:
        _LOGGER.error("Afvalwijzer Calendar: Could not find coordinator!")


class AfvalwijzerCalendar(CalendarEntity):
    """Representation of the Afvalwijzer calendar."""

    def __init__(self, coordinator, entry_id: str):
        """Initialize the Afvalwijzer calendar."""
        self.coordinator = coordinator
        self._attr_name = "Afvalwijzer Calendar"
        self._attr_unique_id = f"afvalwijzer_calendar_{entry_id}"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        today = dt_util.now().date()
        include_today = self.coordinator.config.get("include_today", True)
        collector = self.coordinator.config.get(CONF_COLLECTOR, "Afvalwijzer")

        upcoming_events = []
        for waste_type, event_date in self._full_schedule():
            if not include_today and event_date == today:
                continue
            if event_date >= today:
                upcoming_events.append((event_date, waste_type))

        if not upcoming_events:
            return None

        upcoming_events.sort(key=lambda x: x[0])
        next_event_date = upcoming_events[0][0]

        types_on_next_date = []
        for event_date, waste_type in upcoming_events:
            if event_date == next_event_date and waste_type not in types_on_next_date:
                types_on_next_date.append(waste_type)
        summary_text = f"{collector.capitalize()}: {', '.join([wt.capitalize() for wt in types_on_next_date])}"

        return CalendarEvent(
            summary=summary_text,
            start=next_event_date,
            end=next_event_date + timedelta(days=1),
        )

    def _full_schedule(self) -> list[tuple[str, date]]:
        """Return the full pickup schedule as (waste_type, date) pairs.

        Prefers the raw schedule (every future date for every type). Falls
        back to the next-date-per-type data for caches written before the
        raw schedule was stored.
        """
        raw = getattr(self.coordinator, "waste_data_raw", None) or []
        if raw:
            items = ((item.get("type", ""), item.get("date")) for item in raw)
        else:
            source = self.coordinator.waste_data_with_today or {}
            items = source.items()

        exclude_raw = str(self.coordinator.config.get(CONF_EXCLUDE_LIST, ""))
        exclude = {x.strip() for x in exclude_raw.lower().split(",") if x.strip()}

        schedule: list[tuple[str, date]] = []
        for waste_type, value in items:
            event_date = _to_date(value)
            if event_date is None or not waste_type:
                continue
            if waste_type.strip().lower() in exclude:
                continue
            schedule.append((waste_type, event_date))
        return schedule

    async def async_get_events(
        self, hass, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get the calendar events in the requested range."""
        events = []
        today = dt_util.now().date()

        include_today = self.coordinator.config.get("include_today", True)
        collector = self.coordinator.config.get(CONF_COLLECTOR, "Afvalwijzer")

        for waste_type, event_date in self._full_schedule():
            if not include_today and event_date == today:
                continue

            start = event_date
            end = start + timedelta(days=1)

            if start_date.date() <= start <= end_date.date():
                summary_text = f"{collector.capitalize()}: {waste_type.capitalize()}"

                events.append(
                    CalendarEvent(
                        summary=summary_text,
                        start=start,
                        end=end,
                    )
                )

        return events
