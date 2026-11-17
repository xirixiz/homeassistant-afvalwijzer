"""Tests for the Klikogroep collector."""

import pytest
import requests

from custom_components.afvalwijzer.collector import klikogroep
from tests.fakes import FakeResponse, FakeSession

PROVIDER = "oudeijsselstreek"
CALENDAR = {
    "calendar": {
        "2026-11-17": ["GFT", "Restafval"],
        "2026-11-24": ["Papier"],
        "2026-12-01": [],
    }
}


def _get(session):
    return klikogroep.get_waste_data_raw(PROVIDER, "7001AA", "1", "", session=session)


def test_build_url_uses_the_provider_and_address():
    """Every provider has its own host and id."""
    config = klikogroep.SENSOR_COLLECTORS_KLIKOGROEP[PROVIDER]

    url = klikogroep._build_url(PROVIDER, "7001AA", "1")

    assert url == (
        f"https://{config['url']}/MyKliko/wasteCalendarJSON/{config['id']}/7001AA/1"
    )


def test_build_url_rejects_an_unknown_provider():
    """Only the Klikogroep providers are accepted."""
    with pytest.raises(ValueError, match="Invalid provider"):
        klikogroep._build_url("rova", "7001AA", "1")


def test_calendar_is_requested_with_a_user_agent():
    """The integration identifies itself."""
    session = FakeSession(FakeResponse(CALENDAR))

    result = klikogroep._fetch_waste_data_raw_temp(
        session, "https://x/y", timeout=(1, 1), verify=True
    )

    assert result == CALENDAR
    assert session.calls[0][2]["headers"]["User-Agent"] == "homeassistant-afvalwijzer"


def test_waste_data_has_a_pickup_per_type_per_date():
    """Each date lists the types collected that day."""
    assert klikogroep._parse_waste_data_raw(CALENDAR) == [
        {"type": "gft", "date": "2026-11-17"},
        {"type": "restafval", "date": "2026-11-17"},
        {"type": "papier", "date": "2026-11-24"},
    ]


def test_parse_skips_empty_dates_and_codes():
    """Days without types, and empty or missing codes, are skipped."""
    calendar = {
        "calendar": {
            "": ["GFT"],
            "2026-11-17": [None, "", "Papier"],
            "2026-11-18": None,
        }
    }

    assert klikogroep._parse_waste_data_raw({"calendar": calendar["calendar"]}) == [
        {"type": "papier", "date": "2026-11-17"}
    ]


@pytest.mark.parametrize("payload", [{}, {"calendar": None}])
def test_parse_without_a_calendar_is_empty(payload):
    """No calendar key is an empty schedule."""
    assert klikogroep._parse_waste_data_raw(payload) == []


def test_parse_rejects_a_date_in_another_format():
    """A date we can't read fails the refresh."""
    with pytest.raises(ValueError):
        klikogroep._parse_waste_data_raw({"calendar": {"17-11-2026": ["GFT"]}})


def test_get_waste_data_raw_returns_the_schedule():
    """The full flow."""
    assert len(_get(FakeSession(FakeResponse(CALENDAR)))) == 3


@pytest.mark.parametrize("answer", [FakeResponse(None), FakeResponse({})])
def test_get_waste_data_raw_without_data_returns_nothing(answer, caplog):
    """An empty answer is an empty schedule, not an error."""
    assert _get(FakeSession(answer)) == []
    assert "No waste data found!" in caplog.text


def test_get_waste_data_raw_wraps_request_errors():
    """HTTP and network errors are raised as ValueError for the coordinator."""
    with pytest.raises(ValueError):
        _get(FakeSession(FakeResponse({}, status_code=503)))
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
    assert "KlikoGroep request error" in caplog.text


def test_get_waste_data_raw_wraps_invalid_data():
    """A calendar with a date we can't read is raised as ValueError."""
    session = FakeSession(FakeResponse({"calendar": {"17-11-2026": ["GFT"]}}))

    with pytest.raises(ValueError, match="Invalid and/or no data"):
        _get(session)
