"""Calendar for Afvalwijzer."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import dt as dt_util

from .const.const import CONF_COLLECTOR, DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Afvalwijzer calendar."""
    data_instance = hass.data.get(DOMAIN, {}).get(config_entry.entry_id, {}).get("data_instance")

    if data_instance:
        async_add_entities([AfvalwijzerCalendar(data_instance)])
    else:
        _LOGGER.error("Afvalwijzer Calendar: Could not find data_instance!")

class AfvalwijzerCalendar(CalendarEntity):
    """Representation of the Afvalwijzer calendar."""

    def __init__(self, data):
        """Initialize the Afvalwijzer calendar."""
        self._data = data
        self._attr_name = "Afvalwijzer Calendar"
        self._attr_unique_id = "afvalwijzer_calendar_filtered"

    @property
    def event(self):
        """Return the next upcoming event."""
        return None

    async def async_get_events(self, hass, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        """Get the calendar events."""
        events = []
        today = dt_util.now().date()

        include_today = self._data.config.get("include_today", True)
        waste_source = self._data.waste_data_with_today or {}

        # Get the collector name from the config, fallback to 'Afvalwijzer' if missing
        collector = self._data.config.get(CONF_COLLECTOR, "Afvalwijzer")

        for waste_type, event_date in waste_source.items():
            if not isinstance(event_date, datetime):
                continue

            event_date_only = event_date.date()

            if not include_today and event_date_only == today:
                continue

            start = dt_util.start_of_local_day(event_date)
            end = start + timedelta(days=1)

            if start_date <= start <= end_date:
                # Format: "Collector: WasteType" (e.g., "Mijnafvalwijzer: Papier")
                summary_text = f"{collector.capitalize()}: {waste_type.capitalize()}"

                events.append(
                    CalendarEvent(
                        summary=summary_text,
                        start=start,
                        end=end,
                        all_day=True,
                    )
                )

        return events
