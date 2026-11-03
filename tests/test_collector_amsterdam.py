"""Tests for Amsterdam's first-weekday-of-the-month collections."""

from datetime import datetime

import pytest

from custom_components.afvalwijzer.collector import amsterdam


@pytest.mark.parametrize("hour", [0, 9, 23])
def test_monthly_collection_includes_today(hour):
    """Keep today's first-Tuesday pickup for the whole collection day."""
    item = {
        "afvalwijzerOphaaldagen": "dinsdag",
        "afvalwijzerAfvalkalenderFrequentie": "1evandemaand",
    }

    dates = amsterdam._process_collection_dates(item, datetime(2026, 11, 3, hour))

    assert dates[0] == datetime(2026, 11, 3)
    assert dates[1] == datetime(2026, 12, 1)


@pytest.mark.parametrize(
    "frequency", ["1evandemaand", " 1e van de maand ", "1EVANDEMAAND"]
)
def test_monthly_frequency_variants(frequency):
    """Accept the frequency regardless of spacing or case."""
    item = {
        "afvalwijzerOphaaldagen": "dinsdag",
        "afvalwijzerAfvalkalenderFrequentie": frequency,
    }

    dates = amsterdam._process_collection_dates(item, datetime(2026, 11, 4))

    assert dates[0] == datetime(2026, 12, 1)


def test_monthly_collection_excludes_yesterday():
    """Drop the monthly pickup once its collection day has passed."""
    dates = amsterdam._generate_first_weekday_dates_for_year(2, datetime(2026, 11, 4))

    assert dates[0] == datetime(2026, 12, 1)
    assert len(dates) == 12


@pytest.mark.parametrize("weekday", range(1, 8))
def test_monthly_collection_weekdays_and_year_rollover(weekday):
    """Generate the first matching weekday across the December/January boundary."""
    dates = amsterdam._generate_first_weekday_dates_for_year(
        weekday, datetime(2026, 12, 1)
    )

    assert len(dates) == 13
    assert (dates[0].year, dates[0].month) == (2026, 12)
    assert (dates[1].year, dates[1].month) == (2027, 1)
    assert (dates[-1].year, dates[-1].month) == (2027, 12)
    assert all(d.isoweekday() == weekday and 1 <= d.day <= 7 for d in dates)


def test_parse_waste_data_raw_monthly_paper():
    """A monthly paper item yields formatted dates instead of a parse error."""
    items = [
        {
            "afvalwijzerFractieCode": "papier",
            "afvalwijzerOphaaldagen": "dinsdag",
            "afvalwijzerAfvalkalenderFrequentie": "1evandemaand",
        }
    ]

    result = amsterdam._parse_waste_data_raw(items)

    assert result
    assert all(
        datetime.strptime(r["date"], "%Y-%m-%d").isoweekday() == 2
        and datetime.strptime(r["date"], "%Y-%m-%d").day <= 7
        for r in result
    )
