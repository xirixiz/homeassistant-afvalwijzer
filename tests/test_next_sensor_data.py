"""Tests for the next-collection sensor data."""

from datetime import datetime
import logging
from unittest.mock import patch

import pytest

from custom_components.afvalwijzer.common.next_sensor_data import NextSensorData

NOW = "custom_components.afvalwijzer.common.next_sensor_data.dt_util.now"
TODAY = datetime(2026, 11, 13, 12, 0)


def _waste(*pairs):
    return [{"type": kind, "date": datetime(2026, 11, day)} for kind, day in pairs]


def _data(waste, label="geen"):
    with patch(NOW, return_value=TODAY):
        return NextSensorData(waste, label)


def test_next_date_type_and_days_come_from_the_first_future_pickup():
    """The earliest pickup after today decides all three values."""
    sensor = _data(_waste(("papier", 20), ("gft", 16), ("pmd", 27)))

    assert sensor.next_sensor_data == {
        "next_date": datetime(2026, 11, 16),
        "next_in_days": 3,
        "next_type": "gft",
    }


def test_pickups_on_the_same_day_are_joined_without_duplicates():
    """Two types on one day are both named, a repeated type once."""
    sensor = _data(_waste(("pmd", 16), ("gft", 16), ("pmd", 16), ("papier", 20)))

    assert sensor.next_sensor_data["next_type"] == "pmd, gft"
    assert sensor.next_sensor_data["next_date"] == datetime(2026, 11, 16)


def test_pickups_today_and_before_do_not_count():
    """The next pickup is strictly after today."""
    sensor = _data(_waste(("gft", 12), ("pmd", 13), ("papier", 14)))

    assert sensor.next_sensor_data["next_type"] == "papier"
    assert sensor.next_sensor_data["next_in_days"] == 1


@pytest.mark.parametrize("waste", [[], _waste(("gft", 13), ("pmd", 1))])
def test_without_a_future_pickup_everything_is_the_default_label(waste):
    """Nothing to come gives the label in every field."""
    assert _data(waste, "geen").next_sensor_data == {
        "next_date": "geen",
        "next_in_days": "geen",
        "next_type": "geen",
    }


def test_the_default_label_is_whatever_was_given():
    """The label is not fixed to one word."""
    assert _data([], "none").next_sensor_data["next_type"] == "none"


def test_a_problem_computing_the_days_falls_back_to_the_label(caplog):
    """A date that can't be subtracted is logged and shown as the label."""

    class _Broken:
        def date(self):
            raise RuntimeError("no date")

    sensor = _data(_waste(("gft", 16)))
    sensor.next_waste_date = _Broken()

    with caplog.at_level(logging.ERROR):
        assert sensor._get_next_waste_in_days() == "geen"
    assert "Error occurred in _get_next_waste_in_days" in caplog.text


def test_a_problem_finding_the_type_falls_back_to_the_label(caplog):
    """Pickups without a type are logged and shown as the label."""
    sensor = _data(_waste(("gft", 16)))
    sensor.waste_data_after_date_selected = [{"date": datetime(2026, 11, 16)}]

    with caplog.at_level(logging.ERROR):
        assert sensor._get_next_waste_type() == ["geen"]
    assert "Error occurred in _get_next_waste_type" in caplog.text


def test_a_problem_building_the_data_gives_an_empty_dict(caplog):
    """A type list that can't be joined is logged and gives no data."""
    sensor = _data(_waste(("gft", 16)))
    sensor.next_waste_type = [1, 2]

    with caplog.at_level(logging.ERROR):
        assert sensor._gen_next_sensor_data() == {}
    assert "Error occurred in _gen_next_sensor_data" in caplog.text
