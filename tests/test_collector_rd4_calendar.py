"""Tests for the RD4 calendar: both years, the answers it can get and the parsing."""

from datetime import datetime
import logging

import pytest
import requests

from custom_components.afvalwijzer.collector import rd4

from .fakes import FakeResponse, FakeSession

YEAR = datetime.now().year


def _answer(*items, success=True):
    return FakeResponse({"success": success, "data": {"items": [list(items)]}})


def _item(date="2099-11-13", type_="gft"):
    return {"date": date, "type": type_}


def _run(session, provider="rd4"):
    return rd4.get_waste_data_raw(
        provider, "6417 AT", "32", "", session=session, timeout=(1, 1)
    )


def test_build_url_has_the_address_and_year_and_refuses_unknown_providers():
    """The URL holds the formatted postal code and the year."""
    url = rd4._build_url("rd4", "6417 at", "32", "A", 2027)

    assert "6417AT" in url
    assert "2027" in url
    with pytest.raises(ValueError, match="Invalid provider"):
        rd4._build_url("nonexistent", "6417AT", "32", "", 2027)


@pytest.mark.parametrize(
    "payload",
    [
        None,
        {},
        {"success": False, "data": {"items": [[_item()]]}},
        {"success": True, "data": {"items": []}},
        {"success": True, "data": {}},
        {"success": True},
        {"success": True, "data": {"items": [None]}},
    ],
)
def test_an_answer_without_pickups_is_an_empty_list(payload):
    """No data, an unknown address or no items all mean nothing to show."""
    session = FakeSession(FakeResponse(payload))

    assert (
        rd4._fetch_waste_data_raw_temp(
            session, "https://x", timeout=(1, 1), verify=True
        )
        == []
    )


def test_both_years_are_fetched_and_joined():
    """The calendars of the current and the next year make one schedule."""
    session = FakeSession(
        _answer(_item("2099-12-30")), _answer(_item("2100-01-13", "papier"))
    )

    assert _run(session) == [
        {"type": "gft", "date": "2099-12-30"},
        {"type": "papier", "date": "2100-01-13"},
    ]
    assert f"{YEAR}" in session.urls()[0]
    assert f"{YEAR + 1}" in session.urls()[1]


@pytest.mark.parametrize(
    "failure",
    [
        FakeResponse(status_code=404),
        FakeResponse(json_error=True),
        requests.exceptions.ConnectionError("down"),
    ],
)
def test_next_years_calendar_failing_is_not_an_error(failure, caplog):
    """Next year may not be published yet; this year's data is still returned."""
    session = FakeSession(_answer(_item()), failure)

    with caplog.at_level(logging.DEBUG):
        assert _run(session) == [{"type": "gft", "date": "2099-11-13"}]


def test_no_data_for_either_year_is_logged(caplog):
    """Two empty answers log that nothing was found and return an empty list."""
    session = FakeSession(FakeResponse({}), FakeResponse({}))

    with caplog.at_level(logging.ERROR):
        assert _run(session) == []

    assert "No waste data found or address not found" in caplog.text


def test_this_years_failure_is_a_value_error_without_the_address():
    """The first request failing is reported by its type."""
    session = FakeSession(FakeResponse(status_code=503))

    with pytest.raises(ValueError, match=r"request failed \(HTTPError 503\)") as raised:
        _run(session)
    assert "6417" not in str(raised.value)


def test_a_date_in_another_format_is_invalid_data():
    """A date that isn't year-month-day is reported as invalid data."""
    session = FakeSession(_answer(_item("13-11-2099")), _answer())

    with pytest.raises(ValueError, match="Invalid and/or no data received"):
        _run(session)


def test_parse_skips_items_without_a_date_or_a_type():
    """Incomplete entries are dropped, the rest is kept."""
    items = [
        {"type": "gft"},
        {"date": "2099-11-13"},
        {"date": "2099-11-13", "type": ""},
    ]
    items += [_item("2099-11-14", "Papier ")]

    assert rd4._parse_waste_data_raw(items) == [
        {"type": "papier", "date": "2099-11-14"}
    ]


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        ({"data": [1, 2]}, [1, 2]),
        ({"data": {"a": 1}}, {"a": 1}),
        ([1, 2], [1, 2]),
        ({"other": 1}, {"other": 1}),
        ("text", "text"),
    ],
)
def test_app_data_unwraps_the_data_key_when_there_is_one(payload, expected):
    """App answers come with or without a data wrapper."""
    assert rd4._app_data(FakeResponse(payload)) == expected


def test_app_data_raises_for_an_error_status():
    """A failed app request is an HTTP error, not data."""
    with pytest.raises(requests.exceptions.HTTPError):
        rd4._app_data(FakeResponse({"data": 1}, status_code=500))


def test_unreadable_notification_data_gives_no_notifications(monkeypatch, caplog):
    """Notifications that can't be read are a warning, never an error."""

    def _broken(*_args, **_kwargs):
        raise KeyError("data")

    monkeypatch.setattr(rd4, "_start_session_for_address", _broken)
    rd4._SESSION_CACHE.clear()

    with caplog.at_level(logging.WARNING):
        result = rd4.get_notification_data_raw(
            "rd4", "6417AT", "32", "", session=FakeSession(FakeResponse({}))
        )

    assert result == []
    assert "RD4: invalid notification data (KeyError)" in caplog.text
    rd4._SESSION_CACHE.clear()
