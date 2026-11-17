"""Tests for parsing the DeAfvalApp answer and its error handling."""

import pytest

from custom_components.afvalwijzer.collector import deafvalapp

from .fakes import FakeResponse, FakeSession


def _run(session, provider="deafvalapp"):
    return deafvalapp.get_waste_data_raw(
        provider, "1234AB", "5", "", session=session, timeout=(1, 1)
    )


def test_build_url_holds_the_address_and_refuses_unknown_providers():
    """The URL carries the postal code, number and suffix."""
    url = deafvalapp._build_url("deafvalapp", "1234AB", "5", "B")

    assert url.startswith("https://dataservice.deafvalapp.nl/")
    assert "1234AB" in url
    with pytest.raises(ValueError, match="Invalid provider"):
        deafvalapp._build_url("nonexistent", "1234AB", "5", "")


def test_every_row_gives_the_dates_of_its_type():
    """Each row is a type followed by its dates and a closing semicolon."""
    text = "gft;13-11-2026;27-11-2026;\nPapier;20-11-2026;\n"

    assert deafvalapp._parse_waste_data_raw(text) == [
        {"type": "gft", "date": "2026-11-13"},
        {"type": "gft", "date": "2026-11-27"},
        {"type": "papier", "date": "2026-11-20"},
    ]


def test_blank_rows_and_empty_dates_are_skipped():
    """Empty lines, spaces and empty date cells cost nothing."""
    text = "\n  \ngft; 13-11-2026 ; ;27-11-2026;\n\r\n"

    assert deafvalapp._parse_waste_data_raw(text) == [
        {"type": "gft", "date": "2026-11-13"},
        {"type": "gft", "date": "2026-11-27"},
    ]


def test_a_row_without_dates_gives_nothing():
    """A type with no dates has nothing to show."""
    assert deafvalapp._parse_waste_data_raw("gft\ngft;\n") == []


def test_nothing_in_gives_nothing_out():
    """An empty body is an empty list."""
    assert deafvalapp._parse_waste_data_raw("") == []


def test_the_flow_returns_the_pickups():
    """A normal answer is fetched, then parsed."""
    session = FakeSession(FakeResponse(text="gft;13-11-2026;\n"))

    assert _run(session) == [{"type": "gft", "date": "2026-11-13"}]
    assert session.calls[0][2]["allow_redirects"] is False


def test_an_empty_answer_gives_no_pickups(caplog):
    """An empty body is logged and gives an empty list."""
    assert _run(FakeSession(FakeResponse(text=""))) == []
    assert "No waste data found" in caplog.text


@pytest.mark.parametrize("text", ["gft;2026-11-13;\n", "gft;not a date;\n"])
def test_a_date_in_another_format_is_invalid_data(text):
    """A date that doesn't read as day-month-year is reported as invalid data."""
    session = FakeSession(FakeResponse(text=text))

    with pytest.raises(ValueError, match="Invalid and/or no data received"):
        _run(session)


def test_a_redirect_is_refused_without_the_address():
    """A redirect is an error, and it doesn't carry the address."""
    session = FakeSession(FakeResponse(status_code=302, text="moved"))

    with pytest.raises(ValueError, match="request failed") as raised:
        _run(session)
    assert "1234AB" not in str(raised.value)


def test_an_unknown_provider_is_refused():
    """The provider is checked before anything is requested."""
    session = FakeSession(FakeResponse(text=""))

    with pytest.raises(ValueError, match="Invalid provider"):
        _run(session, provider="nonexistent")
    assert session.calls == []
