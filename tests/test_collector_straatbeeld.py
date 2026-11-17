"""Tests for the Straatbeeld collector."""

import pytest
import requests

from custom_components.afvalwijzer.collector import straatbeeld
from tests.fakes import FakeResponse, FakeSession

PAYLOAD = {
    "collections": {
        "2026": {
            "11": [
                {
                    "date": {"formatted": "2026-11-24"},
                    "data": [{"name": "Papier"}, {"name": "GFT"}],
                },
                {"date": {"formatted": "2026-11-17"}, "data": [{"name": "Restafval"}]},
            ],
            "12": [{"date": {"formatted": "2026-12-01"}, "data": [{"name": "GFT"}]}],
        }
    }
}


def _get(session, **kwargs):
    return straatbeeld.get_waste_data_raw(
        "straatbeeld", "1111 aa", 5, " b ", session=session, **kwargs
    )


def test_build_url_removes_the_trailing_slash():
    """The provider's base URL is used without a trailing slash."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(
            straatbeeld.SENSOR_COLLECTORS_STRAATBEELD, "test", "https://x.nl/"
        )
        assert straatbeeld._build_url("test") == "https://x.nl"


def test_build_url_rejects_an_unknown_provider():
    """Only the Straatbeeld providers are accepted."""
    with pytest.raises(ValueError, match="Invalid provider"):
        straatbeeld._build_url("rova")


def test_calendar_is_requested_with_the_address():
    """The address goes in the JSON body of a POST."""
    session = FakeSession(FakeResponse(PAYLOAD))

    straatbeeld._fetch_waste_data_raw_temp(
        session, "https://x.nl", "1111AA", "5", "B", timeout=(1, 1), verify=True
    )

    method, url, kwargs = session.calls[0]
    assert (method, url) == ("POST", "https://x.nl/v1/waste-calendar")
    assert kwargs["json"] == {
        "postal_code": "1111AA",
        "house_number": "5",
        "house_letter": "B",
    }
    assert kwargs["headers"]["accept"] == "application/json"


def test_waste_data_is_sorted_by_date_and_type():
    """The months and days of the answer are flattened and sorted."""
    assert straatbeeld._parse_waste_data_raw(PAYLOAD) == [
        {"type": "restafval", "date": "2026-11-17"},
        {"type": "gft", "date": "2026-11-24"},
        {"type": "papier", "date": "2026-11-24"},
        {"type": "gft", "date": "2026-12-01"},
    ]


def test_parse_skips_entries_of_the_wrong_shape():
    """A month that isn't a mapping, a day that isn't a list or object, or no name."""
    payload = {
        "collections": {
            "2026": {
                "11": "oops",
                "12": [
                    "oops",
                    {"date": None, "data": [{"name": "GFT"}]},
                    {"date": {"formatted": ""}, "data": [{"name": "GFT"}]},
                    {"date": {"formatted": "2026-12-01"}, "data": [{"name": ""}, {}]},
                    {"date": {"formatted": "2026-12-08"}, "data": None},
                ],
                "13": {"not": "a list"},
            },
            "2027": "oops",
        }
    }

    assert straatbeeld._parse_waste_data_raw(payload) == []


def test_parse_rejects_a_date_in_another_format():
    """A date we can't read fails the refresh."""
    payload = {
        "collections": {
            "2026": {
                "11": [{"date": {"formatted": "17-11-2026"}, "data": [{"name": "GFT"}]}]
            }
        }
    }

    with pytest.raises(ValueError):
        straatbeeld._parse_waste_data_raw(payload)


def test_get_waste_data_raw_returns_the_schedule():
    """The full flow with an address as the user typed it."""
    session = FakeSession(FakeResponse(PAYLOAD))

    result = _get(session)

    assert len(result) == 4
    assert session.calls[0][2]["json"]["postal_code"] == "1111AA"
    assert session.calls[0][2]["json"]["house_number"] == "5"
    assert session.calls[0][2]["json"]["house_letter"] == "b"


@pytest.mark.parametrize("answer", [FakeResponse(None), FakeResponse({})])
def test_get_waste_data_raw_without_data_returns_nothing(answer, caplog):
    """An empty answer is an empty schedule, not an error."""
    assert _get(FakeSession(answer)) == []
    assert "No Waste data found!" in caplog.text


def test_get_waste_data_raw_wraps_request_errors():
    """HTTP errors are raised as ValueError for the coordinator."""
    with pytest.raises(ValueError):
        _get(FakeSession(FakeResponse({}, status_code=503)))
    with pytest.raises(ValueError):
        _get(FakeSession(requests.exceptions.ConnectionError("down")))


def test_get_waste_data_raw_wraps_invalid_data(caplog):
    """A body of the wrong shape is raised as ValueError."""
    payload = {
        "collections": {
            "2026": {
                "11": [{"date": {"formatted": "17-11-2026"}, "data": [{"name": "GFT"}]}]
            }
        }
    }
    session = FakeSession(FakeResponse(payload))

    with pytest.raises(ValueError, match="Invalid and/or no data"):
        _get(session)
    assert "STRAATBEELD: Invalid and/or no data received" in caplog.text


def test_get_waste_data_raw_rejects_an_unknown_provider():
    """Only the Straatbeeld providers are accepted."""
    with pytest.raises(ValueError):
        straatbeeld.get_waste_data_raw("rova", "1111AA", "5", "", session=FakeSession())
