"""Tests for the Omrin collector (login, GraphQL calendar)."""

import pytest
import requests

from custom_components.afvalwijzer.collector import omrin
from tests.fakes import FakeResponse, FakeSession

LOGIN_OK = {"success": True, "data": {"accessToken": "tok-123"}}


def _calendar(*items):
    return {"data": {"fetchCalendar": list(items)}}


def _item(waste_type, date):
    return {"type": waste_type, "date": date}


def _get(session, **kwargs):
    return omrin.get_waste_data_raw(
        "omrin", "8431 zb", "19", "", session=session, **kwargs
    )


# --- token and login ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("token", "expected"),
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("abc", "abc"),
        ("  abc  ", "abc"),
        ("Bearer abc", "abc"),
        ("bearer   abc ", "abc"),
    ],
)
def test_normalize_token(token, expected):
    """A token can be given with or without the Bearer prefix."""
    assert omrin._normalize_token(token) == expected


def test_login_sends_the_address_and_returns_the_token():
    """The app login is address only (no e-mail or password)."""
    session = FakeSession(FakeResponse(LOGIN_OK))

    token = omrin._login(
        session,
        "https://api",
        "8431 zb",
        "19",
        "A",
        timeout=(1, 1),
        verify=True,
        device_id="dev-1",
    )

    assert token == "tok-123"
    method, url, kwargs = session.calls[0]
    assert (method, url) == ("POST", "https://api/api/auth/login")
    assert kwargs["json"]["PostalCode"] == "8431 zb"  # as given
    assert kwargs["json"]["HouseNumber"] == 19
    assert kwargs["json"]["HouseNumberExtension"] == "A"
    assert kwargs["json"]["DeviceId"] == "dev-1"
    assert kwargs["json"]["Email"] is None and kwargs["json"]["Password"] is None


def test_login_makes_up_a_device_id_when_none_is_given():
    """Every login without a device id gets a fresh one."""
    session = FakeSession(FakeResponse(LOGIN_OK))

    omrin._login(
        session, "https://api", "8431ZB", "19", "", timeout=(1, 1), verify=True
    )
    omrin._login(
        session, "https://api", "8431ZB", "19", "", timeout=(1, 1), verify=True
    )

    first, second = (call[2]["json"]["DeviceId"] for call in session.calls)
    assert first and second and first != second


@pytest.mark.parametrize(
    ("answer", "message"),
    [
        (
            FakeResponse({"success": False, "errors": ["Onbekend adres"]}),
            "Login failed",
        ),
        (FakeResponse({"success": True, "data": None}), "Login failed"),
        (FakeResponse(None), "Login failed"),  # an empty body
        (FakeResponse({"success": True, "data": {"accessToken": ""}}), "Not logged in"),
    ],
)
def test_login_failures_are_value_errors(answer, message):
    """An answer without a token is reported, with the provider's errors."""
    with pytest.raises(ValueError, match=message):
        omrin._login(
            FakeSession(answer),
            "https://api",
            "8431ZB",
            "19",
            "",
            timeout=(1, 1),
            verify=True,
        )


# --- calendar -----------------------------------------------------------------------


def test_calendar_is_requested_with_the_token():
    """The GraphQL query carries the bearer token and returns the calendar items."""
    session = FakeSession(FakeResponse(_calendar(_item("GFT", "2026-11-17"))))

    result = omrin._fetch_calendar(
        session, "https://api", "tok", timeout=(1, 1), verify=True
    )

    assert result == [_item("GFT", "2026-11-17")]
    method, url, kwargs = session.calls[0]
    assert (method, url) == ("POST", "https://api/graphql")
    assert kwargs["headers"]["Authorization"] == "Bearer tok"
    assert "fetchCalendar" in kwargs["json"]["query"]


@pytest.mark.parametrize(
    "answer",
    [
        FakeResponse({"data": {"fetchCalendar": None}}),
        FakeResponse({"data": None}),
        FakeResponse({}),
        FakeResponse(None),
    ],
)
def test_calendar_without_items_is_empty(answer):
    """No calendar is an empty list, not an error."""
    result = omrin._fetch_calendar(
        FakeSession(answer), "https://api", "tok", timeout=(1, 1), verify=True
    )

    assert result == []


def test_graphql_errors_are_reported():
    """The messages of all GraphQL errors end up in the exception."""
    answer = FakeResponse({"errors": [{"message": "Not authorised"}, {"code": 7}]})

    with pytest.raises(ValueError, match="GraphQL error: Not authorised, {'code': 7}"):
        omrin._fetch_calendar(
            FakeSession(answer), "https://api", "tok", timeout=(1, 1), verify=True
        )


# --- parsing ------------------------------------------------------------------------


def test_parse_maps_types_and_skips_incomplete_items():
    """Items without a date or a type are skipped, the rest is mapped."""
    items = [
        _item("GFT", "2026-11-17"),
        _item("Restafval", ""),
        {"date": "2026-11-18"},
        _item(None, "2026-11-19"),
        _item("Overig", "2026-11-20"),
    ]

    assert omrin._parse_waste_data_raw(items) == [
        {"type": "gft", "date": "2026-11-17"},
        {"type": "overig", "date": "2026-11-20"},
    ]


def test_parse_rejects_a_date_in_another_format():
    """A date we can't read fails the refresh instead of guessing."""
    with pytest.raises(ValueError):
        omrin._parse_waste_data_raw([_item("GFT", "17-11-2026")])


# --- whole flow ---------------------------------------------------------------------


def test_get_waste_data_raw_logs_in_and_reads_the_calendar():
    """Without a token: login first, then the calendar with the token it returned."""
    session = FakeSession(
        FakeResponse(LOGIN_OK), FakeResponse(_calendar(_item("GFT", "2026-11-17")))
    )

    assert _get(session) == [{"type": "gft", "date": "2026-11-17"}]
    assert session.urls() == [omrin_url("/api/auth/login"), omrin_url("/graphql")]
    assert session.calls[1][2]["headers"]["Authorization"] == "Bearer tok-123"


def test_get_waste_data_raw_skips_the_login_with_a_token():
    """A stored token goes straight to the calendar."""
    session = FakeSession(FakeResponse(_calendar(_item("GFT", "2026-11-17"))))

    result = _get(session, token="Bearer stored")

    assert result == [{"type": "gft", "date": "2026-11-17"}]
    assert session.urls() == [omrin_url("/graphql")]
    assert session.calls[0][2]["headers"]["Authorization"] == "Bearer stored"


def test_get_waste_data_raw_wraps_request_errors():
    """Network errors are raised as ValueError for the coordinator."""
    session = FakeSession(requests.exceptions.ConnectionError("down"))

    with pytest.raises(ValueError):
        _get(session)


def test_get_waste_data_raw_rejects_an_unknown_provider():
    """Only the Omrin provider is accepted."""
    with pytest.raises(ValueError, match="Invalid provider"):
        omrin.get_waste_data_raw("rova", "8431ZB", "19", "", session=FakeSession())


def omrin_url(path):
    """Return the Omrin API URL for a path."""
    return f"{omrin.SENSOR_COLLECTORS_OMRIN['omrin']}{path}"
