"""Calendar entity for Afvalwijzer."""

from __future__ import annotations

from datetime import date, datetime, timedelta
import logging

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.core import callback
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util, slugify

from .common.sensor_utils import (
    address_key,
    build_device_info,
    icon_for_waste_type,
    initial_color_for_waste_type,
)
from .const.const import (
    CONF_COLLECTOR,
    CONF_EXCLUDE_LIST,
    CONF_SEPARATE_CALENDARS,
    DEFAULT_SEPARATE_CALENDARS,
    DOMAIN,
    SENSOR_PREFIX,
)

_LOGGER = logging.getLogger(__name__)

# unique_id used by the calendar entity before it was scoped per config
# entry in 2026.1018-b02; anyone who ran 2026.1015 through the builds
# before that has an orphan under it. Safe to remove after 2027-08.
_LEGACY_UNIQUE_ID = "afvalwijzer_calendar_filtered"

# Waste type names that are abbreviations and should be fully uppercased
# in event summaries instead of capitalized ("GFT", not "Gft").
_ABBREVIATIONS = {"gft", "pmd", "kca"}


def _display_type(waste_type: str) -> str:
    """Return a human-friendly display name for a waste type."""
    name = waste_type.strip()
    if name.lower() in _ABBREVIATIONS:
        return name.upper()
    return name.capitalize()


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


def _raw_schedule(
    coordinator, *, waste_type: str | None = None
) -> list[tuple[str, date]]:
    """Return the pickup schedule as (waste_type, date) pairs.

    Prefers the raw schedule (every future date for every type). Falls back
    to the next-date-per-type data for caches written before the raw
    schedule was stored. If waste_type is given, only that type's pickups
    are returned.
    """
    raw = getattr(coordinator, "waste_data_raw", None) or []
    if raw:
        items = ((item.get("type", ""), item.get("date")) for item in raw)
    else:
        _LOGGER.debug(
            "No raw schedule on coordinator; falling back to next-per-type data"
        )
        source = coordinator.waste_data_with_today or {}
        items = source.items()

    exclude_raw = str(coordinator.config.get(CONF_EXCLUDE_LIST, ""))
    exclude = {x.strip() for x in exclude_raw.lower().split(",") if x.strip()}

    schedule: list[tuple[str, date]] = []
    for item_type, value in items:
        if not item_type:
            continue
        if waste_type is not None and item_type.strip().lower() != waste_type.lower():
            continue
        if item_type.strip().lower() in exclude:
            continue
        event_date = _to_date(value)
        if event_date is None:
            continue
        schedule.append((item_type, event_date))
    return schedule


@callback
def _async_remove_legacy_calendar(hass) -> None:
    """Remove the orphaned pre-2026.1018 calendar entity, if present."""
    registry = er.async_get(hass)
    if entity_id := registry.async_get_entity_id("calendar", DOMAIN, _LEGACY_UNIQUE_ID):
        registry.async_remove(entity_id)


@callback
def _async_remove_stale_calendars(hass, entry_id: str, separate: bool) -> None:
    """Remove calendar entities that don't belong in the current mode.

    An options change reloads the config entry, but HA doesn't delete
    registry entries just because they stop being created on setup - without
    this, switching separate_calendars leaves the old mode's entities behind
    as permanently-unavailable orphans instead of actually going away.
    """
    registry = er.async_get(hass)
    combined_unique_id = f"afvalwijzer_calendar_{entry_id}"

    for entry in er.async_entries_for_config_entry(registry, entry_id):
        if entry.domain != "calendar":
            continue
        is_combined = entry.unique_id == combined_unique_id
        if is_combined == separate:
            registry.async_remove(entry.entity_id)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Afvalwijzer calendar(s)."""
    entry_id = getattr(config_entry, "entry_id", "test_entry_id")
    coordinator = hass.data.get(DOMAIN, {}).get(entry_id, {}).get("coordinator")

    _async_remove_legacy_calendar(hass)

    if not coordinator:
        _LOGGER.error("Afvalwijzer Calendar: Could not find coordinator!")
        return

    separate = bool(
        coordinator.config.get(CONF_SEPARATE_CALENDARS, DEFAULT_SEPARATE_CALENDARS)
    )

    _async_remove_stale_calendars(hass, entry_id, separate)

    if not separate:
        _LOGGER.debug(
            "Setting up Afvalwijzer calendar for entry: %s (schedule: %d entries)",
            entry_id,
            len(getattr(coordinator, "waste_data_raw", None) or []),
        )
        async_add_entities([AfvalwijzerCalendar(coordinator, entry_id)])
        return

    # Grows but never shrinks: a type that stops appearing in the feed
    # keeps its calendar rather than having it vanish out from under
    # anyone using it on a dashboard.
    known_types: set[str] = set()

    @callback
    def _async_add_new_calendars() -> None:
        """Add a calendar for any waste type not seen before."""
        new_entities = []
        for waste_type in coordinator.waste_data_with_today or {}:
            if waste_type not in known_types:
                known_types.add(waste_type)
                new_entities.append(
                    AfvalwijzerTypeCalendar(coordinator, entry_id, waste_type)
                )
        if new_entities:
            _LOGGER.debug("Adding %d per-type calendar(s).", len(new_entities))
            async_add_entities(new_entities)

    _async_add_new_calendars()
    config_entry.async_on_unload(
        coordinator.async_add_listener(_async_add_new_calendars)
    )


class _AfvalwijzerCalendarBase(CalendarEntity):
    """Shared event logic for the combined and per-type calendar entities."""

    _waste_type: str | None = None

    def __init__(self, coordinator):
        """Initialize the calendar base."""
        self.coordinator = coordinator

    @property
    def device_info(self):
        """Group all calendars for the same address under one device."""
        return build_device_info(self.coordinator.config)

    @property
    def event(self) -> CalendarEvent | None:
        """Return the next upcoming event."""
        today = dt_util.now().date()
        include_today = self.coordinator.config.get("include_today", True)
        collector = self.coordinator.config.get(CONF_COLLECTOR, "Afvalwijzer")

        upcoming_events = [
            (event_date, waste_type)
            for waste_type, event_date in _raw_schedule(
                self.coordinator, waste_type=self._waste_type
            )
            if event_date >= today and (include_today or event_date != today)
        ]

        if not upcoming_events:
            return None

        upcoming_events.sort(key=lambda x: x[0])
        next_event_date = upcoming_events[0][0]

        types_on_next_date = []
        for event_date, waste_type in upcoming_events:
            if event_date == next_event_date and waste_type not in types_on_next_date:
                types_on_next_date.append(waste_type)
        summary_text = f"{collector.capitalize()}: {', '.join([_display_type(wt) for wt in types_on_next_date])}"

        return CalendarEvent(
            summary=summary_text,
            start=next_event_date,
            end=next_event_date + timedelta(days=1),
        )

    async def async_get_events(
        self, hass, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Get the calendar events in the requested range."""
        events = []
        today = dt_util.now().date()

        include_today = self.coordinator.config.get("include_today", True)
        collector = self.coordinator.config.get(CONF_COLLECTOR, "Afvalwijzer")

        schedule = _raw_schedule(self.coordinator, waste_type=self._waste_type)
        for waste_type, event_date in schedule:
            if not include_today and event_date == today:
                continue

            start = event_date
            end = start + timedelta(days=1)

            if start_date.date() <= start <= end_date.date():
                summary_text = f"{collector.capitalize()}: {_display_type(waste_type)}"

                events.append(
                    CalendarEvent(
                        summary=summary_text,
                        start=start,
                        end=end,
                    )
                )

        _LOGGER.debug(
            "Calendar returning %d event(s) between %s and %s (full schedule: %d entries)",
            len(events),
            start_date.date(),
            end_date.date(),
            len(schedule),
        )
        return events


class AfvalwijzerCalendar(_AfvalwijzerCalendarBase):
    """The combined calendar covering every waste type."""

    def __init__(self, coordinator, entry_id: str):
        """Initialize the Afvalwijzer calendar."""
        super().__init__(coordinator)
        self._attr_name = "Afvalwijzer Calendar"
        self._attr_unique_id = f"afvalwijzer_calendar_{entry_id}"

        addr = address_key(coordinator.config)
        self.entity_id = f"calendar.{slugify(SENSOR_PREFIX + addr)}"


class AfvalwijzerTypeCalendar(_AfvalwijzerCalendarBase):
    """A calendar scoped to a single waste type.

    Lets a dashboard assign a distinct color per type, since HA's calendar
    card supports per-calendar colors but not per-event colors.
    """

    def __init__(self, coordinator, entry_id: str, waste_type: str):
        """Initialize a per-waste-type Afvalwijzer calendar."""
        super().__init__(coordinator)
        self._waste_type = waste_type
        self._attr_name = f"Afvalwijzer {_display_type(waste_type)} Calendar"
        self._attr_unique_id = f"afvalwijzer_calendar_{entry_id}_{waste_type}"
        self._attr_icon = icon_for_waste_type(waste_type, default="mdi:calendar")
        # One-time suggested color for this calendar (applied only when the
        # entity is first created - the user can freely change it afterward).
        if initial_color := initial_color_for_waste_type(waste_type):
            self._attr_initial_color = initial_color

        addr = address_key(coordinator.config)
        self.entity_id = f"calendar.{slugify(SENSOR_PREFIX + addr + '_' + waste_type)}"
