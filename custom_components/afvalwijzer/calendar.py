from __future__ import annotations
from datetime import datetime
import logging
from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import dt as dt_util
from .const.const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Afvalwijzer calendar."""
    # Retrieve the data instance saved by sensor.py
    data_instance = hass.data.get(DOMAIN, {}).get(config_entry.entry_id, {}).get("data_instance")

    if data_instance:
        async_add_entities([AfvalwijzerCalendar(data_instance)])
    else:
        _LOGGER.error("Afvalwijzer Calendar: Could not find data_instance!")

class AfvalwijzerCalendar(CalendarEntity):
    """Representation of the Afvalwijzer Calendar."""

    def __init__(self, data):
        """Initialize the Afvalwijzer Calendar entity."""
        self._data = data
        self._attr_name = "Afvalwijzer Calendar"
        self._attr_unique_id = "afvalwijzer_calendar_raw"

    @property
    def event(self):
        """Return the next upcoming event."""
        return None

    async def async_get_events(self, hass, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        """Return events in a specific time frame."""
        events = []
        today = dt_util.now().date()

        # Access config from the data instance to see if "exclude today" is active
        # Assuming config is a dict with 'include_today'
        include_today = self._data.config.get("include_today", True)

        # Use waste_data_with_today as the unfiltered source
        waste_source = self._data.waste_data_with_today or {}

        for waste_type, event_date in waste_source.items():
            if not isinstance(event_date, datetime):
                continue

            event_date_only = event_date.date()

            # If "include_today" is False, filter out today's items
            if not include_today and event_date_only == today:
                continue

            start = dt_util.start_of_local_day(event_date)
            end = dt_util.end_of_local_day(event_date)

            if start_date <= start <= end_date:
                events.append(CalendarEvent(summary=waste_type.capitalize(), start=start, end=end))

        return events