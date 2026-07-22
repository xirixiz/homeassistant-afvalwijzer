"""Test calendar for AfvalWijzer."""

from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from custom_components.afvalwijzer.calendar import AfvalwijzerCalendar


@pytest.mark.asyncio
async def test_calendar_event_parsing():
    """Test that the calendar handles mixed date types correctly."""
    mock_data = MagicMock()
    mock_data.config = {"include_today": True, "provider": "afvalthuis"}

    mock_data.waste_data_with_today = {
        "gft": "2026-07-09",
        "pmd": date(2026, 7, 10),
        "restafval": datetime(2026, 7, 11),
        "papier": "2026-07-12T00:00:00",
    }

    calendar = AfvalwijzerCalendar(mock_data, "test_entry_id")

    start_date = datetime(2026, 7, 1)
    end_date = datetime(2026, 7, 31)

    events = await calendar.async_get_events(None, start_date, end_date)

    assert len(events) == 4
    assert events[0].summary == "Afvalthuis: Gft"
    assert events[1].summary == "Afvalthuis: Pmd"
    assert events[2].summary == "Afvalthuis: Restafval"
    assert events[3].summary == "Afvalthuis: Papier"


@pytest.mark.asyncio
async def test_calendar_handles_cache_restored_iso_strings():
    """Data restored from cache stores datetimes as full ISO strings.

    Regression test: these were silently dropped because only the
    YYYY-MM-DD format was parsed.
    """
    mock_data = MagicMock()
    mock_data.config = {"include_today": True, "provider": "afvalthuis"}

    mock_data.waste_data_with_today = {
        "gft": "2026-07-09T00:00:00",
        "restafval": "2026-07-10T00:00:00+02:00",
        "geen_datum": "geen",
    }

    calendar = AfvalwijzerCalendar(mock_data, "test_entry_id")

    events = await calendar.async_get_events(
        None, datetime(2026, 7, 1), datetime(2026, 7, 31)
    )

    assert len(events) == 2
    assert events[0].start == date(2026, 7, 9)
    assert events[1].start == date(2026, 7, 10)
