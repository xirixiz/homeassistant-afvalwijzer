"""Days sensor tests for Afvalwijzer."""

from datetime import date, datetime
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
