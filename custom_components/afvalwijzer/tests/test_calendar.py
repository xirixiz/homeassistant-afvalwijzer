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
    }

    calendar = AfvalwijzerCalendar(mock_data)

    start_date = datetime(2026, 7, 1)
    end_date = datetime(2026, 7, 31)

    events = await calendar.async_get_events(None, start_date, end_date)

    assert len(events) == 3
    assert events[0].summary == "Afvalthuis: Gft"
    assert events[1].summary == "Afvalthuis: Pmd"
    assert events[2].summary == "Afvalthuis: Restafval"
