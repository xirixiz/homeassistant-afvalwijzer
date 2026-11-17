"""Tests for the iCalendar collector."""

from datetime import datetime

import pytest

from custom_components.afvalwijzer.collector import icalendar

from .fakes import FakeResponse, FakeSession

ICAL = (
    "BEGIN:VCALENDAR\r\nBEGIN:VEVENT\r\nSUMMARY:Papierinzameling\r\n"
    "DTSTART;VALUE=DATE:20261113\r\nEND:VEVENT\r\nEND:VCALENDAR"
)


def _run(session, provider="borsele", suffix=""):
    return icalendar.get_waste_data_raw(
        provider, "1234AB", "5", suffix, session=session, timeout=(1, 1)
    )


def test_build_url_fills_in_year_address_and_suffix():
    """Each provider has its own URL pattern."""
    assert (
        icalendar._build_url("borsele", 2026, "1234AB", "5", "A")
        == "https://afvalkalender.borsele.nl/afval/afvalkalender/2026/1234AB-5A.ics"
    )
    assert (
        icalendar._build_url("edam-volendam", 2026, "1234AB", "5", "")
        == "https://www.edam-volendam.nl/trash-calendar/download/1234AB/5/?year=2026"
    )


def test_build_url_refuses_an_unknown_provider():
    """Only listed providers have a URL."""
    with pytest.raises(ValueError, match="Invalid provider"):
        icalendar._build_url("nonexistent", 2026, "1234AB", "5", "")


def test_flow_downloads_the_calendar_of_this_year():
    """The request is for the current year's calendar, and its events are parsed."""
    session = FakeSession(FakeResponse(text=ICAL))

    result = _run(session, suffix="B")

    assert result == [{"type": "papier", "date": "2026-11-13"}]
    year = datetime.today().year
    assert session.urls() == [
        f"https://afvalkalender.borsele.nl/afval/afvalkalender/{year}/1234AB-5B.ics"
    ]


def test_flow_with_an_empty_calendar_gives_no_pickups(caplog):
    """An empty body is logged and returns an empty list."""
    assert _run(FakeSession(FakeResponse(text=""))) == []
    assert "No waste data found" in caplog.text


def test_flow_turns_an_http_error_into_a_value_error():
    """The error describes the failure, not the address."""
    session = FakeSession(FakeResponse(status_code=404))

    with pytest.raises(ValueError, match=r"request failed \(HTTPError 404\)") as raised:
        _run(session)
    assert "1234AB" not in str(raised.value)


def test_flow_with_an_unreadable_calendar_is_a_value_error(monkeypatch):
    """A calendar the parser rejects is reported as invalid data."""

    def _broken(*_args, **_kwargs):
        raise ValueError("bad date")

    monkeypatch.setattr(icalendar, "parse_ical_waste_data", _broken)

    with pytest.raises(ValueError, match="Invalid and/or no data received"):
        _run(FakeSession(FakeResponse(text=ICAL)))
