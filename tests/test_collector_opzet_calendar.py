"""Tests for the Opzet full-calendar support."""

from datetime import date, timedelta

import pytest
import requests

from custom_components.afvalwijzer.collector import opzet

TODAY = date.today()
IN_5 = (TODAY + timedelta(days=5)).isoformat()
IN_12 = (TODAY + timedelta(days=12)).isoformat()
IN_19 = (TODAY + timedelta(days=19)).isoformat()
YESTERDAY = (TODAY - timedelta(days=1)).isoformat()

STREAMS = [
    {"id": 1, "menu_title": "GFT", "ophaaldatum": IN_5},
    {"id": 2, "menu_title": "Restafval", "ophaaldatum": IN_12},
    {"id": 3, "menu_title": "Papier", "ophaaldatum": IN_19},
]


class FakeResponse:
    """Minimal requests.Response stand-in."""

    def __init__(self, payload, status_code=200):
        """Store the payload and status code."""
        self._payload = payload
        self.status_code = status_code

    def json(self):
        """Return the payload."""
        return self._payload

    def raise_for_status(self):
        """Raise HTTPError for error statuses."""
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)


class FakeSession:
    """Session answering GET requests by URL fragment."""

    def __init__(self, calendar_by_year):
        """Store the calendar responses by year."""
        self.calendar_by_year = calendar_by_year

    def get(self, url, **_kwargs):
        """Answer address, stream and calendar requests."""
        if "/kalender/" in url:
            year = int(url.rsplit("/", 1)[1])
            response = self.calendar_by_year.get(
                year, FakeResponse({}, status_code=404)
            )
            if isinstance(response, Exception):
                raise response
            return response
        if url.endswith("/afvalstromen"):
            return FakeResponse(STREAMS)
        return FakeResponse([{"bagId": "bag1"}])


@pytest.fixture(autouse=True)
def _clear_bag_cache():
    opzet._BAG_ID_CACHE.clear()
    yield
    opzet._BAG_ID_CACHE.clear()


def _run(calendar_by_year):
    return opzet.get_waste_data_raw(
        "hvc", "1234AB", "1", "", session=FakeSession(calendar_by_year)
    )


def _dates(result, waste_type):
    return sorted(item["date"] for item in result if item["type"] == waste_type)


def test_calendar_adds_pickups_beyond_the_next_one():
    """The calendar entries are added to the next pickups."""
    later = (TODAY + timedelta(days=19)).isoformat()
    calendar = FakeResponse(
        [
            {"afvalstroom_id": 1, "ophaaldatum": IN_5},
            {"afvalstroom_id": 1, "ophaaldatum": later},
        ]
    )

    result = _run({TODAY.year: calendar, TODAY.year + 1: calendar})

    # The same response answers both years, so duplicates must be collapsed.
    assert _dates(result, "gft") == sorted({IN_5, later})
    assert len(result) == len({(i["type"], i["date"]) for i in result})


def test_stream_missing_from_calendar_keeps_its_next_pickup():
    """A stream the calendar leaves out still has its next pickup."""
    calendar = FakeResponse([{"afvalstroom_id": 1, "ophaaldatum": IN_5}])

    result = _run({TODAY.year: calendar, TODAY.year + 1: FakeResponse([])})

    assert _dates(result, "restafval") == [IN_12]
    assert _dates(result, "papier") == [IN_19]


def test_without_calendar_the_next_pickups_are_returned():
    """When the calendar endpoint is unavailable the behaviour is unchanged."""
    result = _run({})

    assert sorted(item["date"] for item in result) == sorted([IN_5, IN_12, IN_19])


def test_calendar_request_errors_are_ignored():
    """A connection error on the calendar does not fail the refresh."""
    error = requests.exceptions.ConnectionError("boom")

    result = _run({TODAY.year: error, TODAY.year + 1: error})

    assert len(result) == 3


def test_invalid_calendar_entries_are_skipped():
    """Bad entries are skipped without costing the valid ones."""
    calendar = FakeResponse(
        [
            "not an object",
            {"afvalstroom_id": 99, "ophaaldatum": IN_5},
            {"afvalstroom_id": 1, "ophaaldatum": "garbage"},
            {"afvalstroom_id": 1},
            {"afvalstroom_id": 1, "ophaaldatum": YESTERDAY},
            {"afvalstroom_id": 2, "ophaaldatum": IN_19},
        ]
    )

    result = _run(
        {TODAY.year: calendar, TODAY.year + 1: FakeResponse({"not": "a list"})}
    )

    assert _dates(result, "gft") == [IN_5]
    assert _dates(result, "restafval") == sorted([IN_12, IN_19])
