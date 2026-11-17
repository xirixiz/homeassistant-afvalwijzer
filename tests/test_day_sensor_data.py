"""Days sensor tests for Afvalwijzer."""

from datetime import date, datetime
import logging
from unittest.mock import patch

import pytest

from custom_components.afvalwijzer.common.day_sensor_data import DaySensorData


@pytest.mark.parametrize(
    "date_input",
    [
        "2026-07-09",
        date(2026, 7, 9),
        datetime(2026, 7, 9, 0, 0),
    ],
)
@patch("custom_components.afvalwijzer.common.day_sensor_data.dt_util.now")
def test_day_sensor_data_type_variations(mock_now, date_input):
    """Test that DaySensorData correctly parses today regardless of input type."""
    mock_now.return_value = datetime(2026, 7, 9, 12, 0)

    waste_data_formatted = [
        {"type": "gft", "date": date_input},
        {"type": "pmd", "date": "2026-07-10"},
    ]

    sensor_data = DaySensorData(waste_data_formatted, "geen")

    assert sensor_data.day_sensor_data["today"] == "gft"
    assert sensor_data.day_sensor_data["tomorrow"] == "pmd"
    assert sensor_data.day_sensor_data["day_after_tomorrow"] == "geen"


@patch("custom_components.afvalwijzer.common.day_sensor_data.dt_util.now")
def test_day_sensor_data_collects_each_day_and_removes_duplicates(mock_now):
    """Several types on a day are joined; a repeated type appears once."""
    mock_now.return_value = datetime(2026, 7, 9, 12, 0)
    waste = [
        {"type": "gft", "date": datetime(2026, 7, 9)},
        {"type": "pmd", "date": datetime(2026, 7, 9)},
        {"type": "gft", "date": date(2026, 7, 9)},
        {"type": "papier", "date": "2026-07-11"},
        {"type": "restafval", "date": datetime(2026, 7, 20)},
    ]

    assert DaySensorData(waste, "geen").day_sensor_data == {
        "today": "gft, pmd",
        "tomorrow": "geen",
        "day_after_tomorrow": "papier",
    }


@patch("custom_components.afvalwijzer.common.day_sensor_data.dt_util.now")
def test_day_sensor_data_ignores_dates_it_cannot_read(mock_now):
    """A string that isn't a date, or another type, matches no day."""
    mock_now.return_value = datetime(2026, 7, 9, 12, 0)
    waste = [
        {"type": "gft", "date": "09-07-2026"},
        {"type": "pmd", "date": 20260709},
    ]

    assert DaySensorData(waste, "geen").day_sensor_data["today"] == "geen"


@patch("custom_components.afvalwijzer.common.day_sensor_data.dt_util.now")
def test_day_sensor_data_falls_back_to_the_label_on_bad_items(mock_now, caplog):
    """An item without a type is logged and the day shows the label."""
    mock_now.return_value = datetime(2026, 7, 9, 12, 0)

    with caplog.at_level(logging.ERROR):
        data = DaySensorData([{"date": datetime(2026, 7, 9)}], "geen").day_sensor_data

    assert data == {"today": "geen", "tomorrow": "geen", "day_after_tomorrow": "geen"}
    assert "Error occurred in _gen_day_sensor" in caplog.text


@patch("custom_components.afvalwijzer.common.day_sensor_data.dt_util.now")
def test_day_sensor_data_with_a_broken_label_gives_a_partial_dict(mock_now, caplog):
    """A label that can't be joined is logged; what was built so far is kept."""
    mock_now.return_value = datetime(2026, 7, 9, 12, 0)

    with caplog.at_level(logging.ERROR):
        data = DaySensorData([], 5).day_sensor_data

    assert data == {}
    assert "Error occurred in _gen_day_sensor_data" in caplog.text
