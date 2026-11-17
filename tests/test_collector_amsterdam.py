"""Tests for Amsterdam's first-weekday-of-the-month collections."""

from datetime import datetime, timedelta
import json

import pytest
import requests

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


# --- date parsing ------------------------------------------------------------------

TODAY = datetime(2027, 3, 3)  # a Wednesday in ISO week 9 (odd)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("05-11-26", datetime(2026, 11, 5)),
        ("05-11-2026", datetime(2026, 11, 5)),
        ("05-11", datetime(2027, 11, 5)),  # no year: the year of "today"
        ("  05-11-26  ", datetime(2026, 11, 5)),
    ],
)
def test_parse_date_formats(text, expected):
    """The API writes dates with a two or four digit year, or without a year."""
    assert amsterdam._parse_date(text, TODAY) == expected


@pytest.mark.parametrize("text", ["", "   ", None])
def test_parse_date_blank_is_none(text):
    """Nothing to parse is not an error."""
    assert amsterdam._parse_date(text, TODAY) is None


def test_parse_date_unknown_format_is_logged(caplog):
    """A date in an unknown format is reported and skipped."""
    assert amsterdam._parse_date("woensdag", TODAY) is None
    assert "Unable to process date: woensdag" in caplog.text


def test_date_in_future_keeps_only_later_days():
    """Today itself is not "in the future" for explicit dates."""
    dates = [TODAY - timedelta(days=1), TODAY, TODAY + timedelta(days=1)]

    assert amsterdam._date_in_future(dates, TODAY) == [TODAY + timedelta(days=1)]


# --- weekday and week parity -------------------------------------------------------


@pytest.mark.parametrize("weekday", range(1, 8))
def test_weekly_day_delta_is_the_days_until_the_next_weekday(weekday):
    """Without a frequency: today counts, otherwise the next such weekday."""
    delta = amsterdam._calculate_day_delta(weekday, TODAY)

    assert delta == (weekday - TODAY.isoweekday()) % 7
    assert (TODAY + timedelta(days=delta)).isoweekday() == weekday


def _days_until(weekday, today, parity):
    """Brute force: days until the next such weekday in an ISO week of this parity."""
    for delta in range(22):
        day = today + timedelta(days=delta)
        if day.isoweekday() == weekday and day.isocalendar()[1] % 2 == parity:
            return delta
    raise AssertionError("no matching day")


@pytest.mark.parametrize(("frequency", "parity"), [("oneven", 1), ("even", 0)])
def test_odd_and_even_week_day_delta_matches_the_calendar(frequency, parity):
    """Compare with a brute force search, for every day of two ordinary years."""
    for offset in range(2 * 365):
        today = datetime(2027, 1, 4) + timedelta(days=offset)
        for weekday in range(1, 8):
            assert amsterdam._calculate_day_delta(weekday, today, frequency) == (
                _days_until(weekday, today, parity)
            ), (today.date(), weekday)


def test_day_delta_examples():
    """Wednesday 3 March 2027 is in odd week 9."""
    delta = amsterdam._calculate_day_delta
    assert delta(3, TODAY, "oneven") == 0  # today is the odd-week Wednesday
    assert delta(3, TODAY, "even") == 7  # next week
    assert delta(1, TODAY, "oneven") == 12  # Monday of odd week 11
    assert delta(1, TODAY, "even") == 5  # Monday of even week 10


def test_weekly_dates_are_a_year_of_equal_steps():
    """53 weekly dates, starting with the first matching day."""
    dates = amsterdam._generate_dates_for_year(0, 1, TODAY)

    assert len(dates) == 53
    assert dates[0] == TODAY
    assert {(b - a).days for a, b in zip(dates, dates[1:], strict=False)} == {7}


def _item(weekdays, frequency):
    return {
        "afvalwijzerOphaaldagen": weekdays,
        "afvalwijzerAfvalkalenderFrequentie": frequency,
    }


def _in_53_week_year(day):
    """ISO years with 53 weeks have two odd weeks in a row at the year change."""
    return datetime(day.isocalendar()[0], 12, 28).isocalendar()[1] == 53


@pytest.mark.parametrize(
    ("frequency", "parity"),
    [("oneven weken", 1), ("even weken", 0), ("oneven week", 1), ("even week", 0)],
)
def test_odd_and_even_weeks_follow_the_iso_week_number(frequency, parity):
    """Every date is in the right ISO week, over the 53 week year 2026 and its borders.

    _calculate_day_delta alone is one week off in the last two weeks of 2026, where
    weeks 53 and 1 are both odd. The generated list corrects that, which is what
    this checks: right weekday and parity, in order, none in the past, none missing.
    """
    for offset in range(100):
        today = datetime(2026, 11, 1) + timedelta(days=offset)
        for weekday, name in enumerate(amsterdam.WEEKDAY_MAP, start=1):
            dates = amsterdam._process_collection_dates(_item(name, frequency), today)

            assert dates == sorted(set(dates)), (today.date(), name)
            assert all(d.isoweekday() == weekday for d in dates)
            assert all(d.isocalendar()[1] % 2 == parity for d in dates)
            assert all(d >= today for d in dates)
            assert dates[0] == today + timedelta(
                days=_days_until(weekday, today, parity)
            )
            assert len(dates) in (26, 27, 28)
            for earlier, later in zip(dates, dates[1:], strict=False):
                if (later - earlier).days != 14:
                    assert _in_53_week_year(earlier)
                    assert earlier.isocalendar()[0] != later.isocalendar()[0]


def test_odd_and_even_week_examples():
    """Wednesdays from 3 March 2027, which is in odd week 9."""
    odd = amsterdam._process_collection_dates(_item("woensdag", "oneven weken"), TODAY)
    even = amsterdam._process_collection_dates(_item("woensdag", "even weken"), TODAY)

    assert [d.strftime("%m-%d") for d in odd[:4]] == [
        "03-03",
        "03-17",
        "03-31",
        "04-14",
    ]
    assert [d.strftime("%m-%d") for d in even[:4]] == [
        "03-10",
        "03-24",
        "04-07",
        "04-21",
    ]


# --- collection days and explicit dates --------------------------------------------


def test_without_a_frequency_the_item_is_collected_weekly():
    """Items like "stoep" have no frequency: every week on the collection day."""
    dates = amsterdam._process_collection_dates(_item("woensdag", ""), TODAY)

    assert len(dates) == 53
    assert dates[0] == TODAY
    assert {(b - a).days for a, b in zip(dates, dates[1:], strict=False)} == {7}


def test_several_collection_days_give_dates_for_each_weekday():
    """The item "maandag, donderdag" is collected on both days."""
    dates = amsterdam._process_collection_dates(_item("maandag, donderdag", ""), TODAY)

    assert {d.isoweekday() for d in dates} == {1, 4}
    assert len(dates) == 106


def test_unknown_collection_days_are_skipped():
    """A value that is not a weekday gives no dates."""
    assert amsterdam._process_collection_dates(_item("n.v.t.", ""), TODAY) == []
    assert amsterdam._process_collection_dates(_item("", "even weken"), TODAY) == []


def test_explicit_dates_in_the_past_are_dropped():
    """A list of dates keeps only the ones after today."""
    frequency = "01-03-27 05-03-27, 19-03-2027"

    dates = amsterdam._process_collection_dates(_item("vrijdag", frequency), TODAY)

    assert dates == [datetime(2027, 3, 5), datetime(2027, 3, 19)]


def test_explicit_dates_without_a_year_use_the_current_year():
    """A date like 12-03 is in the year of today."""
    dates = amsterdam._process_collection_dates(_item("vrijdag", "12-03"), TODAY)

    assert dates == [datetime(2027, 3, 12)]


def test_explicit_dates_are_not_repeated_per_collection_day():
    """With two collection days a listed date must still appear once."""
    item = _item("dinsdag, vrijdag", "05-03-27, 19-03-27")

    dates = amsterdam._process_collection_dates(item, TODAY)

    assert dates == [datetime(2027, 3, 5), datetime(2027, 3, 19)]


def test_leap_day_without_a_year_parses_in_a_leap_year():
    """29 February exists in 2028 and not in 2027.

    Parsing a day and month alone cannot do that (and is deprecated since
    Python 3.13), so the year is added to the text before parsing.
    """
    assert amsterdam._parse_date("29-02", datetime(2028, 1, 10)) == datetime(
        2028, 2, 29
    )
    assert amsterdam._parse_date("29-02", TODAY) is None


# --- API items ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("item", "valid"),
    [
        (
            {
                "afvalwijzerAfvalkalenderFrequentie": "even weken",
                "afvalwijzerFractieCode": "GFT",
                "afvalwijzerOphaaldagen": "dinsdag",
            },
            True,
        ),
        (
            {
                "afvalwijzerWaar": "aan de stoep",
                "afvalwijzerFractieCode": "Restafval",
                "afvalwijzerOphaaldagen": "dinsdag",
            },
            True,
        ),
        (  # neither a frequency nor "stoep"
            {
                "afvalwijzerWaar": "container",
                "afvalwijzerFractieCode": "Restafval",
                "afvalwijzerOphaaldagen": "dinsdag",
            },
            False,
        ),
        (  # no waste type
            {
                "afvalwijzerAfvalkalenderFrequentie": "even weken",
                "afvalwijzerOphaaldagen": "dinsdag",
            },
            False,
        ),
        (  # no collection days
            {
                "afvalwijzerAfvalkalenderFrequentie": "even weken",
                "afvalwijzerFractieCode": "GFT",
            },
            False,
        ),
        ({}, False),
    ],
)
def test_item_validity(item, valid):
    """An item needs a frequency or "stoep", a waste type and collection days."""
    assert amsterdam._is_item_valid(item) is valid


@pytest.mark.freeze_time("2027-03-03 12:00:00")
def test_parse_waste_data_raw_sorts_and_skips_invalid_items():
    """The schedule is formatted, sorted by date and type, and skips bad items."""
    items = [
        {
            "afvalwijzerFractieCode": "GFT",
            "afvalwijzerOphaaldagen": "vrijdag",
            "afvalwijzerAfvalkalenderFrequentie": "05-03-27, 19-03-27",
        },
        {
            "afvalwijzerFractieCode": "Papier",
            "afvalwijzerOphaaldagen": "vrijdag",
            "afvalwijzerAfvalkalenderFrequentie": "05-03-27",
        },
        {"afvalwijzerFractieCode": "Glas"},  # invalid
    ]

    assert amsterdam._parse_waste_data_raw(items) == [
        {"date": "2027-03-05", "type": "gft"},
        {"date": "2027-03-05", "type": "papier"},
        {"date": "2027-03-19", "type": "gft"},
    ]


# --- requests ----------------------------------------------------------------------


def test_query_params_without_a_suffix():
    """Only the postal code and house number."""
    assert amsterdam._build_query_params("1011AB", 7, "") == [
        {"postcode": "1011AB", "huisnummer": "7"}
    ]


def test_query_params_try_every_way_of_writing_a_suffix():
    """A suffix is a huisletter or a toevoeging, lower or upper case, or neither."""
    params = amsterdam._build_query_params("1011AB", "7", " B ")

    base = {"postcode": "1011AB", "huisnummer": "7"}
    assert params == [
        {**base, "huisletter": "b"},
        {**base, "huisnummertoevoeging": "b"},
        {**base, "huisletter": "B"},
        {**base, "huisnummertoevoeging": "B"},
        base,
    ]


@pytest.mark.parametrize(
    ("text", "valid"), [("", False), ("x" * 220, False), ("x" * 221, True)]
)
def test_response_validity(text, valid):
    """The API answers an unknown address with a short body."""
    assert amsterdam._check_response_is_valid(text) is valid


class FakeResponse:
    """Minimal requests.Response stand-in."""

    def __init__(self, payload=None, *, text=None, status_code=200, url="https://x/"):
        """Store the payload; the text defaults to the payload as JSON."""
        self._payload = payload
        self.text = text if text is not None else json.dumps(payload, indent=2)
        self.status_code = status_code
        self.url = url

    def json(self):
        """Return the payload."""
        return self._payload

    def raise_for_status(self):
        """Raise HTTPError for error statuses."""
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)


class FakeSession:
    """Session answering with the next response and remembering the parameters."""

    def __init__(self, *responses):
        """Store the responses, answered in order."""
        self.responses = list(responses)
        self.params = []

    def get(self, url, params=None, **_kwargs):
        """Answer a GET."""
        self.params.append(params)
        return self.responses.pop(0)


ITEMS = {
    "_links": {"self": {"href": "https://api.example/afvalwijzer/?postcode=1011AB"}},
    "_embedded": {
        "afvalwijzer": [
            {
                "afvalwijzerFractieCode": "GFT",
                "afvalwijzerOphaaldagen": "vrijdag",
                "afvalwijzerAfvalkalenderFrequentie": "05-03-27, 19-03-27",
            }
        ]
    },
}


def test_fetch_tries_the_next_suffix_variant_when_the_answer_is_empty():
    """A short body means "not found" for that way of writing the suffix."""
    session = FakeSession(FakeResponse(text="{}"), FakeResponse(ITEMS))
    params = [{"huisletter": "b"}, {"huisnummertoevoeging": "b"}]

    result = amsterdam._fetch_waste_data_raw_temp(
        session, "https://x", params, timeout=(1, 1), verify=True
    )

    assert result == ITEMS
    assert session.params == params


def test_fetch_gives_up_when_no_variant_is_valid():
    """Giving up raises an error without the URL that answered last."""
    session = FakeSession(FakeResponse(text="{}", url="https://x/"))

    with pytest.raises(ValueError, match="Invalid and/or no data"):
        amsterdam._fetch_waste_data_raw_temp(
            session, "https://x", [{"a": "b"}], timeout=(1, 1), verify=True
        )


@pytest.mark.freeze_time("2027-03-03 12:00:00")
def test_get_waste_data_raw_returns_the_schedule():
    """The full flow: query, parse, format."""
    session = FakeSession(FakeResponse(ITEMS))

    result = amsterdam.get_waste_data_raw(
        "amsterdam", "1011 ab", 7, "", session=session
    )

    assert result == [
        {"date": "2027-03-05", "type": "gft"},
        {"date": "2027-03-19", "type": "gft"},
    ]
    assert session.params == [{"postcode": "1011AB", "huisnummer": "7"}]


def test_get_waste_data_raw_without_items_returns_nothing(caplog):
    """An answer without pickups is an empty schedule, not an error."""
    payload = {"_embedded": {"afvalwijzer": []}, "padding": "x" * 250}

    result = amsterdam.get_waste_data_raw(
        "amsterdam", "1011AB", "7", "", session=FakeSession(FakeResponse(payload))
    )

    assert result == []
    assert "No Waste data found!" in caplog.text


def test_get_waste_data_raw_wraps_request_errors():
    """HTTP errors are raised as ValueError for the coordinator."""
    session = FakeSession(FakeResponse({}, text="", status_code=503))

    with pytest.raises(ValueError):
        amsterdam.get_waste_data_raw("amsterdam", "1011AB", "7", "", session=session)


def test_get_waste_data_raw_wraps_invalid_data(caplog):
    """A body that is not what we expect is raised as ValueError."""
    payload = {"_embedded": {"afvalwijzer": 5}, "padding": "x" * 250}
    session = FakeSession(FakeResponse(payload))

    with pytest.raises(ValueError, match="Invalid and/or no data"):
        amsterdam.get_waste_data_raw("amsterdam", "1011AB", "7", "", session=session)


def test_get_waste_data_raw_rejects_an_unknown_provider():
    """Only the Amsterdam provider is accepted."""
    with pytest.raises(ValueError):
        amsterdam.get_waste_data_raw("rova", "1011AB", "7", "", session=FakeSession())
