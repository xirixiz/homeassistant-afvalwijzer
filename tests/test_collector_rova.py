"""Tests for the ROVA collector."""

import pytest
import requests

from custom_components.afvalwijzer.collector import rova
from tests.fakes import FakeResponse, FakeSession

SCHEDULE = [
    {"date": "2026-11-17T00:00:00Z", "wasteType": {"title": "GFT"}},
    {"date": "2026-11-24T00:00:00Z", "wasteType": {"title": "Papier"}},
]


def _get(session):
    return rova.get_waste_data_raw("rova", "7101XJ", "23", "a", session=session)


def test_build_url_contains_the_address_and_an_uppercase_addition():
    """The addition is written in capitals."""
    url = rova._build_url("rova", "7101XJ", "23", " a ")

    assert url.startswith(
        f"{rova.SENSOR_COLLECTORS_ROVA['rova']}/api/waste-calendar/upcoming"
    )
    assert "houseNumber=23" in url
    assert "addition=A&" in url
    assert "postalcode=7101XJ" in url


def test_build_url_without_an_addition_leaves_it_empty():
    """No suffix gives an empty addition."""
    assert "addition=&" in rova._build_url("rova", "7101XJ", "23", None)


def test_build_url_rejects_an_unknown_provider():
    """Only the ROVA provider is accepted."""
    with pytest.raises(ValueError, match="Invalid provider"):
        rova._build_url("rwm", "7101XJ", "23", "")


def test_waste_data_is_mapped_and_dates_trimmed_to_the_day():
    """The API gives a timestamp; only the day is kept."""
    assert rova._parse_waste_data_raw(SCHEDULE) == [
        {"type": "gft", "date": "2026-11-17"},
        {"type": "papier", "date": "2026-11-24"},
    ]


def test_parse_skips_incomplete_items():
    """Items without a date or a title are skipped."""
    items = [
        {"date": "2026-11-17T00:00:00Z"},
        {"date": "2026-11-17T00:00:00Z", "wasteType": None},
        {"date": "2026-11-17T00:00:00Z", "wasteType": {"title": ""}},
        {"wasteType": {"title": "GFT"}},
        {"date": "", "wasteType": {"title": "GFT"}},
        {"date": "2026-11-18T00:00:00Z", "wasteType": {"title": "Restafval"}},
    ]

    assert rova._parse_waste_data_raw(items) == [
        {"type": "restafval", "date": "2026-11-18"}
    ]


def test_parse_rejects_a_date_in_another_format():
    """A date without the time and Z fails the refresh instead of guessing."""
    with pytest.raises(ValueError):
        rova._parse_waste_data_raw(
            [{"date": "2026-11-17", "wasteType": {"title": "GFT"}}]
        )


def test_get_waste_data_raw_returns_the_schedule():
    """The full flow."""
    session = FakeSession(FakeResponse(SCHEDULE))

    assert _get(session) == [
        {"type": "gft", "date": "2026-11-17"},
        {"type": "papier", "date": "2026-11-24"},
    ]
    assert "addition=A" in session.urls()[0]


@pytest.mark.parametrize("answer", [FakeResponse(None), FakeResponse([])])
def test_get_waste_data_raw_without_data_returns_nothing(answer, caplog):
    """An empty answer is an empty schedule, not an error."""
    assert _get(FakeSession(answer)) == []
    assert "No waste data found!" in caplog.text


def test_get_waste_data_raw_wraps_request_errors():
    """HTTP and network errors are raised as ValueError for the coordinator."""
    with pytest.raises(ValueError):
        _get(FakeSession(FakeResponse([], status_code=503)))
    with pytest.raises(ValueError):
        _get(FakeSession(requests.exceptions.ConnectionError("down")))


def test_get_waste_data_raw_wraps_a_body_that_is_not_json(caplog):
    """An HTML error page instead of JSON is raised as ValueError.

    With current requests a JSON decode error is a RequestException, so it is
    reported through the request error path.
    """
    session = FakeSession(FakeResponse(json_error=True))

    with pytest.raises(ValueError):
        _get(session)
    assert "ROVA request error" in caplog.text


def test_get_waste_data_raw_wraps_invalid_data():
    """A schedule with a date we can't read is raised as ValueError."""
    answer = FakeResponse([{"date": "2026-11-17", "wasteType": {"title": "GFT"}}])

    with pytest.raises(ValueError, match="Invalid and/or no data"):
        _get(FakeSession(answer))
