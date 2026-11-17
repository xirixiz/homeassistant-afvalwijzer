"""Tests for the whole Circulus flow: login, address check, calendar and errors."""

import logging

import pytest
import requests

from custom_components.afvalwijzer.collector import circulus

from .fakes import FakeResponse, FakeSession

URL = "https://mijn.circulus.nl"
HOME = FakeResponse(cookies={"CB_SESSION": "x__AT=token&___TS=1"})
REGISTERED = FakeResponse({"success": True}, cookies={"CB_SESSION": "y"})


def _calendar(garbage=None):
    garbage = (
        [{"code": "GFT", "dates": ["2026-11-13", "", None]}]
        if garbage is None
        else garbage
    )
    return FakeResponse({"customData": {"response": {"garbage": garbage}}})


def _run(session, suffix="", provider="circulus"):
    return circulus.get_waste_data_raw(
        provider, "7311AA", "3", suffix, session=session, timeout=(1, 1)
    )


def test_an_unknown_provider_is_refused():
    """Only listed providers have an address."""
    with pytest.raises(ValueError, match="Invalid provider"):
        _run(FakeSession(HOME), provider="nonexistent")


def test_the_flow_sends_the_authenticity_token_and_returns_the_pickups():
    """Home page, registration with the token from the cookie, then the calendar."""
    session = FakeSession(HOME, REGISTERED, _calendar())

    assert _run(session) == [{"type": "gft", "date": "2026-11-13"}]
    assert session.urls()[:2] == [URL, f"{URL}/register/zipcode.json"]
    registration = session.calls[1][2]["data"]
    assert registration == {
        "authenticityToken": "token",
        "zipCode": "7311AA",
        "number": "3",
    }
    assert "/afvalkalender.json?from=" in session.urls()[2]


def test_a_cookie_without_a_token_registers_with_an_empty_one():
    """A session cookie of another shape gives an empty authenticity token."""
    home = FakeResponse(cookies={"CB_SESSION": "plain"})
    session = FakeSession(home, REGISTERED, _calendar())

    _run(session)

    assert session.calls[1][2]["data"]["authenticityToken"] == ""


@pytest.mark.parametrize(
    "registration",
    [FakeResponse({}, cookies={"CB_SESSION": "y"}), FakeResponse({"success": True})],
)
def test_a_registration_without_data_or_cookies_stops_the_flow(registration, caplog):
    """No answer or no logged-in cookie means the login failed."""
    session = FakeSession(HOME, registration)

    with caplog.at_level(logging.ERROR):
        assert _run(session) == []

    assert "login/session failed" in caplog.text
    assert len(session.calls) == 2


def test_a_refused_address_is_logged_with_the_reason(caplog):
    """The reason Circulus gives is in the log."""
    refused = FakeResponse(
        {"success": False, "flashMessage": "Niet bekend"}, cookies={"CB_SESSION": "y"}
    )

    with caplog.at_level(logging.ERROR):
        assert _run(FakeSession(HOME, refused)) == []

    assert "Niet bekend" in caplog.text


def test_a_refused_address_without_a_reason_says_so(caplog):
    """A refusal without text is still explained in the log."""
    refused = FakeResponse({"success": False}, cookies={"CB_SESSION": "y"})

    with caplog.at_level(logging.ERROR):
        _run(FakeSession(HOME, refused))

    assert "no reason given" in caplog.text


def test_an_empty_calendar_gives_no_pickups(caplog):
    """A calendar without garbage entries is logged as no data."""
    session = FakeSession(HOME, REGISTERED, _calendar([]))

    with caplog.at_level(logging.ERROR):
        assert _run(session) == []

    assert "No Waste data found for the selected address" in caplog.text


def test_a_calendar_without_custom_data_is_empty():
    """An answer without the expected structure gives nothing."""
    session = FakeSession(HOME, REGISTERED, FakeResponse({"customData": None}))

    assert _run(session) == []


def test_the_selected_address_is_authenticated_before_the_calendar():
    """With several addresses the chosen one is opened first."""
    several = FakeResponse(
        {
            "success": True,
            "customData": {
                "addresses": [
                    {
                        "address": "Kerklaan 3, 7311AA Apeldoorn",
                        "authenticationUrl": "/authToken?id=1",
                    }
                ]
            },
        },
        cookies={"CB_SESSION": "y"},
    )
    session = FakeSession(HOME, several, FakeResponse(), _calendar())

    assert len(_run(session)) == 1
    assert session.urls()[2] == f"{URL}/authToken?id=1"


def test_no_addresses_selects_nothing():
    """An answer without addresses has nothing to select."""
    assert circulus._maybe_select_address({}, "3", "") == ""
    assert (
        circulus._maybe_select_address({"customData": {"addresses": []}}, "3", "") == ""
    )


def test_a_failing_request_is_a_value_error_without_the_address():
    """The error names the type, not the address."""
    session = FakeSession(requests.exceptions.ConnectionError("https://secret/7311AA"))

    with pytest.raises(
        ValueError, match=r"request failed \(ConnectionError\)"
    ) as raised:
        _run(session)
    assert "7311AA" not in str(raised.value)
