"""Tests for the transformer that turns raw pickups into sensor data."""

from datetime import datetime
from unittest.mock import patch

from custom_components.afvalwijzer.common.waste_data_transformer import (
    WasteDataTransformer,
)

NOW = "custom_components.afvalwijzer.common.waste_data_transformer.dt_util.now"
RAW = [
    {"type": "papier", "date": "2026-11-20"},
    {"type": "gft", "date": "2026-11-13"},
    {"type": "gft", "date": "2026-11-27"},
    {"type": "pmd", "date": "2026-11-12"},
    {"type": "ignore", "date": "2026-11-14"},
    {"type": "restafval", "date": "2026-11-16"},
]


def _transform(exclude_today="true", exclude_list="", raw=RAW):
    with (
        patch(NOW, return_value=datetime(2026, 11, 13, 9, 0)),
        patch(
            "custom_components.afvalwijzer.common.next_sensor_data.dt_util.now",
            return_value=datetime(2026, 11, 13, 9, 0),
        ),
        patch(
            "custom_components.afvalwijzer.common.day_sensor_data.dt_util.now",
            return_value=datetime(2026, 11, 13, 9, 0),
        ),
    ):
        return WasteDataTransformer(raw, exclude_today, exclude_list, "geen")


def test_ignored_types_are_dropped_and_the_rest_is_sorted():
    """Pickups of the type ignore never reach the sensors."""
    sensor = _transform()

    assert [item["type"] for item in sensor.waste_data_raw] == [
        "pmd",
        "gft",
        "restafval",
        "papier",
        "gft",
    ]
    assert "ignore" not in sensor.waste_types_provider


def test_with_today_the_next_pickup_of_each_type_starts_today():
    """A pickup today counts when today is not excluded."""
    sensor = _transform(exclude_today="false")

    assert sensor.waste_data_with_today == {
        "papier": datetime(2026, 11, 20),
        "gft": datetime(2026, 11, 13),
        "pmd": "geen",
        "restafval": datetime(2026, 11, 16),
    }
    assert sensor.waste_data_provider == sensor.waste_data_with_today


def test_without_today_the_next_pickup_of_each_type_starts_tomorrow():
    """A pickup today is skipped when today is excluded."""
    sensor = _transform(exclude_today="true")

    assert sensor.waste_data_without_today == {
        "papier": datetime(2026, 11, 20),
        "gft": datetime(2026, 11, 27),
        "pmd": "geen",
        "restafval": datetime(2026, 11, 16),
    }
    assert sensor.waste_data_provider == sensor.waste_data_without_today


def test_the_exclude_list_removes_types_everywhere():
    """Excluded types are in no sensor and no list; spaces and case don't matter."""
    sensor = _transform(exclude_list=" PMD , gft ,")

    assert sensor.waste_types_provider == ["papier", "restafval"]
    assert sensor.waste_data_with_today.keys() == {"papier", "restafval"}
    assert sensor.waste_data_without_today.keys() == {"papier", "restafval"}


def test_custom_data_has_the_next_and_the_day_sensors():
    """The custom sensors combine the next-pickup and the day data."""
    sensor = _transform(exclude_today="true")

    assert sensor.waste_data_custom == {
        "next_date": datetime(2026, 11, 16),
        "next_in_days": 3,
        "next_type": "restafval",
        "today": "gft",
        "tomorrow": "geen",
        "day_after_tomorrow": "geen",
    }
    assert sensor.waste_types_custom == sorted(sensor.waste_data_custom)


def test_with_today_included_the_next_sensor_still_looks_after_today():
    """The next pickup is after today, whatever the setting."""
    sensor = _transform(exclude_today="no")

    assert sensor.waste_data_custom["next_type"] == "restafval"
    assert sensor.waste_data_custom["today"] == "gft"


def test_without_pickups_there_is_nothing_but_labels():
    """No data gives empty provider data and the label for the custom sensors."""
    sensor = _transform(raw=[])

    assert sensor.waste_data_provider == {}
    assert sensor.waste_types_provider == []
    assert sensor.waste_data_custom["next_type"] == "geen"
    assert sensor.waste_data_custom["today"] == "geen"
