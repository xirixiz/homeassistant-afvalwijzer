"""Tests for the RWM collector."""

import pytest
import requests

from custom_components.afvalwijzer.collector import rwm
from tests.fakes import FakeResponse, FakeSession

SCHEDULE = [
    {"title": "GFT", "ophaaldatum": "2026-11-17"},
    {"title": "Papier", "ophaaldatum": "2026-11-24"},
]


def _get(session):
    return rwm.get_waste_data_raw("rwm", "6105CL", "50", "", session=session)


def test_waste_data_is_mapped_and_dates_kept():
    """Streams as the API returns them."""
    assert rwm._parse_waste_data_raw(SCHEDULE) == [
        {"type": "gft", "date": "2026-11-17"},
        {"type": "papier", "date": "2026-11-24"},
    ]


def test_parse_skips_incomplete_items():
    """Items without a date or a title are skipped."""
    items = [
        {"title": "GFT", "ophaaldatum": ""},
        {"title": "GFT"},
        {"ophaaldatum": "2026-11-17"},
        {"title": "", "ophaaldatum": "2026-11-17"},
        {"title": "Wintertuin", "ophaaldatum": "2026-11-18"},
    ]

    assert rwm._parse_waste_data_raw(items) == [
        {"type": "wintertuin", "date": "2026-11-18"}
    ]


def test_parse_rejects_a_date_in_another_format():
    """A date we can't read fails the refresh."""
    with pytest.raises(ValueError):
        rwm._parse_waste_data_raw([{"title": "GFT", "ophaaldatum": "17-11-2026"}])


def test_get_waste_data_raw_looks_up_the_address_then_the_schedule():
    """The bag id of the address is used to read the schedule."""
    session = FakeSession(FakeResponse([{"bagid": "0123"}]), FakeResponse(SCHEDULE))

    result = _get(session)

    assert result == [
        {"type": "gft", "date": "2026-11-17"},
        {"type": "papier", "date": "2026-11-24"},
    ]
    assert session.urls() == [
        "https://rwm.nl/adressen/6105CL:50",
        "https://rwm.nl/rest/adressen/0123/afvalstromen",
    ]


@pytest.mark.parametrize(
    ("answers", "message"),
    [
        ([FakeResponse([])], "Address not found!"),
        ([FakeResponse(None)], "Address not found!"),
        ([FakeResponse([{"straat": "x"}])], "bagid missing"),
        ([FakeResponse([{"bagid": "0123"}]), FakeResponse([])], "Could not retrieve"),
    ],
)
def test_get_waste_data_raw_returns_nothing_when_something_is_missing(
    answers, message, caplog
):
    """An unknown address or an empty schedule is an empty schedule, logged."""
    assert _get(FakeSession(*answers)) == []
    assert message in caplog.text


def test_get_waste_data_raw_wraps_request_errors():
    """HTTP and network errors are raised as ValueError for the coordinator."""
    with pytest.raises(ValueError):
        _get(FakeSession(FakeResponse([], status_code=503)))
    with pytest.raises(ValueError):
        _get(FakeSession(requests.exceptions.ConnectionError("down")))


def test_get_waste_data_raw_wraps_invalid_data(caplog):
    """A schedule with a date we can't read is raised as ValueError."""
    with pytest.raises(ValueError, match="Invalid and/or no data"):
        _get(
            FakeSession(
                FakeResponse([{"bagid": "0123"}]),
                FakeResponse([{"title": "GFT", "ophaaldatum": "17-11-2026"}]),
            )
        )
    assert "RWM: Invalid and/or no data received" in caplog.text


def test_get_waste_data_raw_rejects_an_unknown_provider():
    """The RWM collector only serves RWM."""
    with pytest.raises(ValueError, match="Invalid provider"):
        rwm.get_waste_data_raw("rova", "6105CL", "50", "", session=FakeSession())
