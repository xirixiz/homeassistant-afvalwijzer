from __future__ import annotations
from datetime import datetime
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import dt as dt_util
from .const.const import DOMAIN

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Afvalwijzer calendar."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    fetch_data = coordinator.fetch_data

    async_add_entities([AfvalwijzerCalendar(fetch_data)])

class AfvalwijzerCalendar(CalendarEntity):
    """Representation of an Afvalwijzer calendar that respects your filters."""

    def __init__(self, fetch_data):
        """Init."""
        self._fetch_data = fetch_data
        self._attr_name = "Afvalwijzer"
        self._attr_unique_id = "afvalwijzer_calendar_filtered"

    @property
    def event(self):
        """Event."""
        return None

    async def async_get_events(self, hass, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        """Return events, filtering out today if the config demands it."""
        events = []

        # Get today's date for comparison
        today = dt_util.now().date()

        # Check if we should exclude today based on your config toggle
        exclude_today = self._fetch_data.exclude_pickup_today.casefold() not in ("false", "no")

        # Iterate over the raw data
        for item in self._fetch_data.waste_data_raw:
            event_date = datetime.strptime(item["date"], "%Y-%m-%d").date()

            # THE FILTER LOGIC:
            # If exclude_today is True, and this event is today, skip it.
            if exclude_today and event_date == today:
                continue

            # Format dates as timezone-aware local midnight
            event_datetime = datetime.combine(event_date, datetime.min.time())
            start = dt_util.start_of_local_day(event_datetime)
            end = dt_util.end_of_local_day(event_datetime)

            # Check if event falls within the range requested by the UI
            if start_date <= start <= end_date:
                events.append(
                    CalendarEvent(
                        summary=item["type"].capitalize(),
                        start=start,
                        end=end,
                    )
                )
        return events