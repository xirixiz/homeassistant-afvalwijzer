"""Dates at the edges: new year, ISO week 53, leap days and daylight saving time.

Most of the integration works with dates, and the bugs there hide where calendars
are awkward: weeks that belong to the other year, February 29th and midnights that
shift. These tests sweep every start date over fifteen years instead of picking a few.
"""

from datetime import date, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

from custom_components.afvalwijzer.collector import amsterdam
from custom_components.afvalwijzer.common import sensor_utils
from custom_components.afvalwijzer.common.day_sensor_data import DaySensorData
from custom_components.afvalwijzer.common.next_sensor_data import NextSensorData
from custom_components.afvalwijzer.common.sensor_utils import (
    as_utc_aware,
    date_to_local_midnight,
)
from custom_components.afvalwijzer.common.waste_data_transformer import (
    WasteDataTransformer,
)

AMSTERDAM = ZoneInfo("Europe/Amsterdam")
WEEKDAYS = list(amsterdam.WEEKDAY_MAP)
# Years with 53 ISO weeks in this span: 2020, 2026 and 2032.
SWEEP_START = datetime(2019, 12, 1)
SWEEP_DAYS = 15 * 365


def _item(weekday, frequency=""):
    return {
        "afvalwijzerOphaaldagen": weekday,
        "afvalwijzerAfvalkalenderFrequentie": frequency,
    }


def _first_matching_day(today, weekday, parity):
    """Return the first day from today on with this weekday in a week of this parity."""
    day = today
    while day.isoweekday() != weekday or day.isocalendar()[1] % 2 != parity:
        day += timedelta(days=1)
    return day


def _starts(step=1):
    return (SWEEP_START + timedelta(days=n) for n in range(0, SWEEP_DAYS, step))


# --- recurring collection over every start date -------------------------------------


def test_weekly_pickups_are_every_seven_days_from_the_first_matching_day():
    """For every start date and weekday: right weekday, 7 days apart, none in the past."""
    for today in _starts():
        for weekday, name in enumerate(WEEKDAYS, start=1):
            dates = amsterdam._process_collection_dates(_item(name), today)

            assert dates[0] >= today
            assert dates[0] < today + timedelta(days=7)
            assert {d.isoweekday() for d in dates} == {weekday}
            assert {(b - a).days for a, b in zip(dates, dates[1:], strict=False)} == {7}


@pytest.mark.parametrize(
    ("frequency", "parity"), [("oneven weken", 1), ("even weken", 0)]
)
def test_odd_and_even_weeks_are_right_for_every_start_date(frequency, parity):
    """Every date is in a week of the right parity, in order and not in the past.

    Weeks 53 and 1 are both odd in a 53 week year, so a fortnight can be a week
    there; that is the only gap that is allowed to differ.
    """
    for today in _starts(step=3):
        for weekday, name in enumerate(WEEKDAYS, start=1):
            dates = amsterdam._process_collection_dates(_item(name, frequency), today)

            context = (today.date(), name)
            assert dates == sorted(set(dates)), context
            assert all(d >= today for d in dates), context
            assert {d.isoweekday() for d in dates} == {weekday}, context
            assert {d.isocalendar()[1] % 2 for d in dates} == {parity}, context
            assert dates[0] == _first_matching_day(today, weekday, parity), context
            for earlier, later in zip(dates, dates[1:], strict=False):
                gap = (later - earlier).days
                assert gap in (14, 7, 21), context
                if gap != 14:
                    assert earlier.isocalendar()[1] in (52, 53), context


def test_the_first_weekday_of_each_month_over_every_start_date():
    """The monthly pickup is on the first such weekday of each month, from today on."""
    for today in _starts(step=2):
        for weekday, name in enumerate(WEEKDAYS, start=1):
            dates = amsterdam._process_collection_dates(
                _item(name, "1e van de maand"), today
            )

            assert dates, (today.date(), name)
            assert all(d.date() >= today.date() for d in dates)
            assert {d.isoweekday() for d in dates} == {weekday}
            assert all(d.day <= 7 for d in dates)
            months = [(d.year, d.month) for d in dates]
            assert months == sorted(set(months)), "one pickup per month, in order"
            # consecutive months, so none is skipped
            for (y1, m1), (y2, m2) in zip(months, months[1:], strict=False):
                assert (y2 * 12 + m2) - (y1 * 12 + m1) == 1


@pytest.mark.parametrize("year", [2020, 2024, 2028, 2032])
def test_a_date_without_a_year_on_leap_day_is_read_in_a_leap_year(year):
    """29 February with no year isn't an error in the leap years it exists in."""
    today = datetime(year, 1, 10)

    assert amsterdam._parse_date("29-02", today) == datetime(year, 2, 29)


# --- the sensors around new year and the leap day -----------------------------------


def _patched_now(now):
    return (
        patch(
            "custom_components.afvalwijzer.common.next_sensor_data.dt_util.now",
            return_value=now,
        ),
        patch(
            "custom_components.afvalwijzer.common.day_sensor_data.dt_util.now",
            return_value=now,
        ),
        patch(
            "custom_components.afvalwijzer.common.waste_data_transformer.dt_util.now",
            return_value=now,
        ),
    )


def _transform(now, pickups, exclude_today="true"):
    first, second, third = _patched_now(now)
    with first, second, third:
        return WasteDataTransformer(pickups, exclude_today, "", "geen")


@pytest.mark.parametrize(
    ("today", "pickup", "days"),
    [
        (datetime(2026, 12, 31, 23, 59), date(2027, 1, 1), 1),
        (datetime(2026, 12, 30, 0, 0), date(2027, 1, 2), 3),
        (datetime(2027, 1, 1, 0, 0), date(2027, 1, 8), 7),
        (datetime(2028, 2, 28, 12, 0), date(2028, 2, 29), 1),
        (datetime(2028, 2, 29, 12, 0), date(2028, 3, 1), 1),
        (datetime(2027, 2, 28, 12, 0), date(2027, 3, 1), 1),
        (datetime(2028, 12, 31, 12, 0), date(2029, 1, 1), 1),
    ],
)
def test_the_next_pickup_across_the_year_and_the_leap_day(today, pickup, days):
    """The days until the next pickup count calendar days, over any boundary."""
    sensor = _transform(today, [{"type": "gft", "date": pickup.isoformat()}])

    assert sensor.waste_data_custom["next_in_days"] == days
    assert sensor.waste_data_custom["next_date"].date() == pickup
    assert sensor.waste_data_custom["next_type"] == "gft"


def test_the_day_sensors_roll_over_into_the_new_year():
    """On 31 December, tomorrow is 1 January and the day after is 2 January."""
    pickups = [
        {"type": "gft", "date": "2026-12-31"},
        {"type": "pmd", "date": "2027-01-01"},
        {"type": "papier", "date": "2027-01-02"},
    ]

    sensor = _transform(datetime(2026, 12, 31, 8, 0), pickups, exclude_today="false")

    assert sensor.waste_data_custom["today"] == "gft"
    assert sensor.waste_data_custom["tomorrow"] == "pmd"
    assert sensor.waste_data_custom["day_after_tomorrow"] == "papier"


def test_the_day_sensors_know_the_leap_day():
    """In a leap year 28 February is followed by the 29th, then March."""
    first, second, third = _patched_now(datetime(2028, 2, 28, 8, 0))
    pickups = [
        {"type": "gft", "date": datetime(2028, 2, 29)},
        {"type": "pmd", "date": datetime(2028, 3, 1)},
    ]
    with first, second, third:
        data = DaySensorData(pickups, "geen").day_sensor_data

    assert data == {"today": "geen", "tomorrow": "gft", "day_after_tomorrow": "pmd"}


def test_the_next_sensor_ignores_the_time_of_day():
    """Late in the evening, a pickup tomorrow is still one day away."""
    first, _second, _third = _patched_now(datetime(2026, 11, 13, 23, 59))
    with first:
        data = NextSensorData(
            [{"type": "gft", "date": datetime(2026, 11, 14)}], "geen"
        ).next_sensor_data

    assert data["next_in_days"] == 1


# --- daylight saving time -----------------------------------------------------------

DST_CHANGES = [
    date(2026, 3, 29),
    date(2026, 10, 25),
    date(2027, 3, 28),
    date(2027, 10, 31),
]


@pytest.mark.parametrize("change", DST_CHANGES)
def test_midnight_is_midnight_on_the_days_the_clocks_change(change):
    """A pickup date keeps its date when it becomes a timestamp and back."""
    with patch.object(sensor_utils.dt_util, "DEFAULT_TIME_ZONE", AMSTERDAM):
        for day in (change - timedelta(days=1), change, change + timedelta(days=1)):
            aware = date_to_local_midnight(day)
            utc = as_utc_aware(datetime(day.year, day.month, day.day))

            assert aware.astimezone(AMSTERDAM).date() == day
            assert aware.astimezone(AMSTERDAM).time().hour == 0
            assert utc.astimezone(AMSTERDAM).date() == day


def test_every_day_of_two_years_survives_the_round_trip():
    """No date shifts when it is converted to a timestamp and read back locally."""
    with patch.object(sensor_utils.dt_util, "DEFAULT_TIME_ZONE", AMSTERDAM):
        day = date(2026, 1, 1)
        while day < date(2028, 1, 1):
            assert date_to_local_midnight(day).astimezone(AMSTERDAM).date() == day
            assert (
                as_utc_aware(datetime.combine(day, datetime.min.time()))
                .astimezone(AMSTERDAM)
                .date()
                == day
            )
            day += timedelta(days=1)
