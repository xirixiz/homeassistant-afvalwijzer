"""Tests for selecting the right Circulus address."""

import pytest
import requests

from custom_components.afvalwijzer.collector import circulus

URL = "https://mijn.circulus.nl"


class FakeResponse:
    """Minimal requests.Response stand-in."""

    def __init__(self, payload=None, cookies=None):
        """Store the payload and cookies."""
        self._payload = payload
        self.cookies = cookies or {}

    def json(self):
        """Return the payload."""
        return self._payload

    def raise_for_status(self):
        """Never fail."""


class FakeSession:
    """Session answering the Circulus registration flow."""

    def __init__(self, registration):
        """Store the registration answer."""
        self.registration = registration
        self.authenticated = None
        self.calendar_requests = 0

    def get(self, url, **_kwargs):
        """Answer the home page, an address selection or the calendar."""
        if url == URL:
            return FakeResponse(cookies={"CB_SESSION": "x__AT=token&___TS=1"})
        if "/authToken" in url:
            self.authenticated = url.split("id=", 1)[1]
            return FakeResponse()
        if "/afvalkalender.json" in url:
            self.calendar_requests += 1
            garbage = [{"code": "GFT", "dates": ["2026-11-13"]}]
            return FakeResponse({"customData": {"response": {"garbage": garbage}}})
        raise AssertionError(f"unexpected URL {url}")

    def post(self, url, **_kwargs):
        """Answer the postal code registration."""
        assert url == f"{URL}/register/zipcode.json"
        return FakeResponse(self.registration, cookies={"CB_SESSION": "y"})


def _multiple(*lines):
    return {
        "success": True,
        "flashMessage": "Aris.address.multiple.found",
        "customData": {
            "addresses": [
                {"address": line, "authenticationUrl": f"/authToken?id={i}"}
                for i, line in enumerate(lines)
            ]
        },
    }


SAME_POSTCODE_TWO_STREETS = _multiple(
    "Kerklaan 3 c, 7311AA Apeldoorn",
    "Van Huutstraat 3, 7311AA Apeldoorn",
    "Kerklaan 3 d, 7311AA Apeldoorn",
)


def _run(registration, house_number="3", suffix=""):
    session = FakeSession(registration)
    result = circulus.get_waste_data_raw(
        "circulus", "7311AA", house_number, suffix, session=session
    )
    return session, result


def test_single_match_needs_no_selection():
    """A unique address is used as registered."""
    session, result = _run({"success": True, "flashMessage": "", "customData": {}})

    assert session.authenticated is None
    assert result == [{"type": "gft", "date": "2026-11-13"}]


def test_without_suffix_prefers_the_bare_house_number():
    """Another street's '3 c' listed first is not picked for plain '3'."""
    session, _ = _run(SAME_POSTCODE_TWO_STREETS)

    assert session.authenticated == "1"


@pytest.mark.parametrize("suffix", ["d", "D"])
def test_suffix_matches_case_insensitively(suffix):
    """The suffix is matched regardless of case."""
    session, _ = _run(SAME_POSTCODE_TWO_STREETS, suffix=suffix)

    assert session.authenticated == "2"


def test_uppercase_suffix_in_the_address_list():
    """Suffixes Circulus writes in capitals, like 'WON', match too."""
    registration = _multiple(
        "Kerklaan 1 a, 7311AA Apeldoorn", "Kerklaan 1 WON, 7311AA Apeldoorn"
    )

    session, _ = _run(registration, house_number="1", suffix="won")

    assert session.authenticated == "1"


def test_without_bare_number_falls_back_to_the_first(caplog):
    """With only suffixed options and no suffix configured, warn and use the first."""
    registration = _multiple(
        "Kerklaan 1 WON, 7311AA Apeldoorn", "Kerklaan 1 a, 7311AA Apeldoorn"
    )

    session, result = _run(registration, house_number="1")

    assert session.authenticated == "0"
    assert result
    assert "Configure a suffix" in caplog.text


def test_unknown_suffix_returns_nothing(caplog):
    """A configured suffix that isn't offered fetches no calendar."""
    session, result = _run(SAME_POSTCODE_TWO_STREETS, suffix="z")

    assert result == []
    assert session.calendar_requests == 0
    assert "no address with suffix 'Z'" in caplog.text


def test_house_number_is_not_matched_as_a_prefix():
    """'13' is not taken for '3'."""
    registration = _multiple(
        "Kerklaan 13, 7311AA Apeldoorn", "Van Huutstraat 3, 7311AA Apeldoorn"
    )

    session, _ = _run(registration)

    assert session.authenticated == "1"


def test_unknown_address_logs_circulus_message(caplog):
    """Circulus's own reason is logged instead of 'No Waste data found'."""
    registration = {
        "success": False,
        "flashMessage": "Het opgegeven adres is niet bij ons bekend.",
    }

    session, result = _run(registration, house_number="5")

    assert result == []
    assert session.calendar_requests == 0
    assert "niet bij ons bekend" in caplog.text
    assert "No Waste data found" not in caplog.text


def test_session_cookie_missing_returns_nothing():
    """Without a session cookie the flow stops early."""
    session = FakeSession({})
    session.get = lambda url, **_kw: FakeResponse(cookies={})

    assert (
        circulus.get_waste_data_raw("circulus", "7311AA", "3", "", session=session)
        == []
    )


def test_request_errors_become_value_errors():
    """Network errors are raised as ValueError for the coordinator."""
    session = FakeSession({})

    def fail(*_args, **_kwargs):
        raise requests.exceptions.ConnectionError("down")

    session.get = fail
    with pytest.raises(ValueError):
        circulus.get_waste_data_raw("circulus", "7311AA", "3", "", session=session)
