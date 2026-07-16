"""Calendar entity for Afvalwijzer."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import dt as dt_util

from .const.const import CONF_COLLECTOR, DOMAIN

_LOGGER = logging.getLogger(__name__)


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
        waste_source = self.coordinator.waste_data_with_today or {}
        collector = self.coordinator.config.get(CONF_COLLECTOR, "Afvalwijzer")

        upcoming_events = []
        for waste_type, event_date in waste_source.items():
            if isinstance(event_date, str):
                try:
                    event_date_only = datetime.strptime(event_date, "%Y-%m-%d").date()
                except ValueError:
                    continue
            elif isinstance(event_date, datetime):
                event_date_only = event_date.date()
            elif isinstance(event_date, date):
                event_date_only = event_date
            else:
                continue

            if not include_today and event_date_only == today:
                continue
            if event_date_only >= today:
                upcoming_events.append((event_date_only, waste_type))

        if not upcoming_events:
            return None

        upcoming_events.sort(key=lambda x: x[0])
        next_event_date = upcoming_events[0][0]

        types_on_next_date = [wt for ed, wt in upcoming_events if ed == next_event_date]
        summary_text = f"{collector.capitalize()}: {', '.join([wt.capitalize() for wt in types_on_next_date])}"

        return CalendarEvent(
            summary=summary_text,
            start=next_event_date,
            end=next_event_date + timedelta(days=1),
        )

    async def async_get_events(
        self, hass, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get the calendar events."""
        events = []
        today = dt_util.now().date()

        include_today = self.coordinator.config.get("include_today", True)
        waste_source = self.coordinator.waste_data_with_today or {}

        collector = self.coordinator.config.get(CONF_COLLECTOR, "Afvalwijzer")

        for waste_type, event_date in waste_source.items():
            if isinstance(event_date, str):
                try:
                    event_date_only = datetime.strptime(event_date, "%Y-%m-%d").date()
                except ValueError:
                    continue
            elif isinstance(event_date, datetime):
                event_date_only = event_date.date()
            elif isinstance(event_date, date):
                event_date_only = event_date
            else:
                continue

            if not include_today and event_date_only == today:
                continue

            start = event_date_only
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
