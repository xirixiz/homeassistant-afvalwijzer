from __future__ import annotations

from datetime import datetime
import logging

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.util import dt as dt_util

from .const.const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Afvalwijzer calendar."""
    _LOGGER.info("Setting up Afvalwijzer Calendar...")

    # Attempt to retrieve the data coordinator
    try:
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        fetch_data = coordinator.fetch_data
        async_add_entities([AfvalwijzerCalendar(fetch_data)])
    except Exception as e:
        _LOGGER.error("Failed to set up Afvalwijzer Calendar: %s", e)

class AfvalwijzerCalendar(CalendarEntity):
    def __init__(self, fetch_data):
        """Initialize the Afvalwijzer calendar entity."""
        self._fetch_data = fetch_data
        self._attr_name = "Afvalwijzer"
        self._attr_unique_id = "afvalwijzer_calendar_filtered"

    @property
    def event(self):
        """Return the next upcoming event, if available."""
        return None

    async def async_get_events(self, hass, start_date: datetime, end_date: datetime) -> list[CalendarEvent]:
        """Fetch events from the Afvalwijzer data source within the specified date range."""
        events = []
        today = dt_util.now().date()
        exclude_today = self._fetch_data.exclude_pickup_today.casefold() not in ("false", "no")

        # LOGGING: See how much data we actually have
        raw_data = getattr(self._fetch_data, 'waste_data_raw', [])
        _LOGGER.info("Calendar fetching events. Raw data items found: %s", len(raw_data))

        for item in raw_data:
            try:
                event_date = datetime.strptime(item["date"], "%Y-%m-%d").date()
                if exclude_today and event_date == today:
                    continue

                start = dt_util.start_of_local_day(datetime.combine(event_date, datetime.min.time()))
                end = dt_util.end_of_local_day(datetime.combine(event_date, datetime.min.time()))

                if start_date <= start <= end_date:
                    events.append(
                        CalendarEvent(
                            summary=item["type"].capitalize(),
                            start=start,
                            end=end,
                        )
                    )
            except Exception as err:
                _LOGGER.error("Error processing calendar event: %s", err)

        _LOGGER.info("Calendar returning %s events", len(events))
        return events
