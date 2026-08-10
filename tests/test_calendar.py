"""Test calendar for AfvalWijzer."""

from datetime import date, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from custom_components.afvalwijzer.calendar import (
    AfvalwijzerCalendar,
    _async_remove_legacy_calendar,
)


def _mock_coordinator(*, raw=None, with_today=None, config=None):
    mock_data = MagicMock()
    mock_data.config = config or {"include_today": True, "provider": "afvalthuis"}
    mock_data.waste_data_raw = raw or []
    mock_data.waste_data_with_today = with_today or {}
    return mock_data


def _registry_entry(entity_id, unique_id, domain="calendar"):
    return SimpleNamespace(entity_id=entity_id, unique_id=unique_id, domain=domain)


@pytest.mark.asyncio
async def test_calendar_event_parsing_fallback():
    """Without a raw schedule the calendar falls back to next-per-type data."""
    mock_data = _mock_coordinator(
        with_today={
            "gft": "2026-07-09",
            "pmd": date(2026, 7, 10),
            "restafval": datetime(2026, 7, 11),
            "papier": "2026-07-12T00:00:00",
        }
    )

    calendar = AfvalwijzerCalendar(mock_data, "test_entry_id")

    events = await calendar.async_get_events(
        None, datetime(2026, 7, 1), datetime(2026, 7, 31)
    )

    assert len(events) == 4
    assert events[0].summary == "Afvalthuis: GFT"
    assert events[1].summary == "Afvalthuis: PMD"
    assert events[2].summary == "Afvalthuis: Restafval"
    assert events[3].summary == "Afvalthuis: Papier"


@pytest.mark.asyncio
async def test_calendar_full_schedule_multiple_dates_per_type():
    """The raw schedule yields every future pickup, not just the next one."""
    mock_data = _mock_coordinator(
        raw=[
            {"type": "gft", "date": "2026-07-09"},
            {"type": "gft", "date": "2026-07-23"},
            {"type": "gft", "date": "2026-08-06"},
            {"type": "restafval", "date": "2026-07-16"},
            {"type": "restafval", "date": "2026-08-13"},
        ]
    )

    calendar = AfvalwijzerCalendar(mock_data, "test_entry_id")

    events = await calendar.async_get_events(
        None, datetime(2026, 7, 1), datetime(2026, 8, 31)
    )
    assert len(events) == 5

    # Only the events inside the requested range are returned
    july_events = await calendar.async_get_events(
        None, datetime(2026, 7, 1), datetime(2026, 7, 31)
    )
    assert len(july_events) == 3
    assert {e.start for e in july_events} == {
        date(2026, 7, 9),
        date(2026, 7, 16),
        date(2026, 7, 23),
    }


@pytest.mark.asyncio
async def test_calendar_full_schedule_handles_cache_iso_strings():
    """Raw schedule entries restored from cache store dates as ISO strings."""
    mock_data = _mock_coordinator(
        raw=[
            {"type": "gft", "date": "2026-07-09T00:00:00"},
            {"type": "restafval", "date": "2026-07-10T00:00:00+02:00"},
            {"type": "kapot", "date": "geen"},
        ]
    )

    calendar = AfvalwijzerCalendar(mock_data, "test_entry_id")

    events = await calendar.async_get_events(
        None, datetime(2026, 7, 1), datetime(2026, 7, 31)
    )

    assert len(events) == 2
    assert events[0].start == date(2026, 7, 9)
    assert events[1].start == date(2026, 7, 10)


@pytest.mark.asyncio
async def test_calendar_respects_exclude_list():
    """Waste types on the exclude list do not appear in the calendar."""
    mock_data = _mock_coordinator(
        raw=[
            {"type": "gft", "date": "2026-07-09"},
            {"type": "papier", "date": "2026-07-10"},
        ],
        config={
            "include_today": True,
            "provider": "afvalthuis",
            "exclude_list": "papier",
        },
    )

    calendar = AfvalwijzerCalendar(mock_data, "test_entry_id")

    events = await calendar.async_get_events(
        None, datetime(2026, 7, 1), datetime(2026, 7, 31)
    )

    assert len(events) == 1
    assert events[0].summary == "Afvalthuis: GFT"


def test_calendar_next_event_groups_types_on_same_date():
    """The next-event state groups all types collected on the same day."""
    today = date.today().isoformat()
    mock_data = _mock_coordinator(
        raw=[
            {"type": "gft", "date": today},
            {"type": "papier", "date": today},
            {"type": "gft", "date": "2099-01-01"},
        ],
        config={"include_today": True, "provider": "mijnafvalwijzer"},
    )

    calendar = AfvalwijzerCalendar(mock_data, "test_entry_id")
    event = calendar.event

    assert event is not None
    assert event.start == date.today()
    assert event.summary == "Mijnafvalwijzer: GFT, Papier"


def test_remove_legacy_calendar_cleans_up_pre_2026_1018_orphan():
    """Anyone updating straight from 2026.1017 has an orphan under the old global unique_id."""
    legacy = _registry_entry(
        "calendar.afvalwijzer_calendar", "afvalwijzer_calendar_filtered"
    )
    registry = MagicMock()

    with (
        patch(
            "custom_components.afvalwijzer.calendar.er.async_get", return_value=registry
        ),
        patch(
            "custom_components.afvalwijzer.calendar.er.async_entries_for_config_entry",
            return_value=[legacy],
        ),
    ):
        _async_remove_legacy_calendar(SimpleNamespace(), "test_entry")

    registry.async_remove.assert_called_once_with("calendar.afvalwijzer_calendar")


def test_remove_legacy_calendar_leaves_current_entity_alone():
    """The current per-entry calendar entity is not mistaken for the legacy one."""
    current = _registry_entry(
        "calendar.afvalwijzer_bonenakker", "afvalwijzer_calendar_test_entry"
    )
    registry = MagicMock()

    with (
        patch(
            "custom_components.afvalwijzer.calendar.er.async_get", return_value=registry
        ),
        patch(
            "custom_components.afvalwijzer.calendar.er.async_entries_for_config_entry",
            return_value=[current],
        ),
    ):
        _async_remove_legacy_calendar(SimpleNamespace(), "test_entry")

    registry.async_remove.assert_not_called()


def test_remove_legacy_calendar_ignores_other_domains():
    """A sensor entity is never mistaken for the legacy calendar entity."""
    sensor_entry = _registry_entry(
        "sensor.afvalwijzer_calendar_filtered",
        "afvalwijzer_calendar_filtered",
        domain="sensor",
    )
    registry = MagicMock()

    with (
        patch(
            "custom_components.afvalwijzer.calendar.er.async_get", return_value=registry
        ),
        patch(
            "custom_components.afvalwijzer.calendar.er.async_entries_for_config_entry",
            return_value=[sensor_entry],
        ),
    ):
        _async_remove_legacy_calendar(SimpleNamespace(), "test_entry")

    registry.async_remove.assert_not_called()
