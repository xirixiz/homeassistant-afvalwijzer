"""Tests for Burgerportaal: sign-in, the address and token caches and the parsing."""

import logging

import pytest
import requests

from custom_components.afvalwijzer.collector import burgerportaal

from .fakes import FakeResponse, FakeSession


@pytest.fixture(autouse=True)
def _clear_caches():
    """Keep the module-level caches from leaking between tests."""
    burgerportaal._AUTH_CACHE.clear()
    burgerportaal._ADDRESS_ID_CACHE.clear()
    yield
    burgerportaal._AUTH_CACHE.clear()
    burgerportaal._ADDRESS_ID_CACHE.clear()


def _ok(payload):
    return FakeResponse(payload, text="x")


def _status(status):
    return FakeResponse(status_code=status, text="x")


SIGNUP = _ok({"refreshToken": "refresh-1"})
TOKEN = _ok({"id_token": "id-1"})
ADDRESSES = _ok([{"addressId": "addr-1", "addition": ""}])
CALENDAR = _ok(
    [
        {"collectionDate": "2026-11-20T00:00:00", "fraction": "Papier"},
        {"collectionDate": "2026-11-13T00:00:00", "fraction": "GFT"},
    ]
)
PICKUPS = [
    {"type": "gft", "date": "2026-11-13"},
    {"type": "papier", "date": "2026-11-20"},
]
KWARGS = {"timeout": (1, 1), "verify": True}


def _run(session, suffix="", **kwargs):
    return burgerportaal.get_waste_data_raw(
        "assen", "1234AB", "5", suffix, session=session, timeout=(1, 1), **kwargs
    )


# --- sign-in -----------------------------------------------------------------------


def test_org_id_of_an_unknown_provider_is_refused():
    """Only listed municipalities have an organisation id."""
    with pytest.raises(ValueError, match="Invalid provider"):
        burgerportaal._build_org_id("nonexistent")


def test_a_given_id_token_is_used_as_is():
    """With a token there is nothing to request."""
    session = FakeSession()

    result = burgerportaal._get_auth_token(
        session, id_token="id-0", refresh_token="ref-0", **KWARGS
    )

    assert result == ("id-0", "ref-0")
    assert session.calls == []


def test_a_refresh_token_is_exchanged_for_an_id_token():
    """The stored refresh token gives a new id token without a new user."""
    session = FakeSession(TOKEN)

    result = burgerportaal._get_auth_token(session, refresh_token="ref-0", **KWARGS)

    assert result == ("id-1", "ref-0")
    assert session.calls[0][2]["data"]["refresh_token"] == "ref-0"
    assert len(session.calls) == 1


@pytest.mark.parametrize("rejection", [_status(400), _ok({})])
def test_a_rejected_refresh_token_creates_a_new_user(rejection, caplog):
    """An expired token, or an answer without an id token, starts over."""
    session = FakeSession(rejection, SIGNUP, TOKEN)

    with caplog.at_level(logging.WARNING):
        result = burgerportaal._get_auth_token(session, refresh_token="old", **KWARGS)

    assert result == ("id-1", "refresh-1")
    assert "stored refresh token was rejected" in caplog.text


def test_signup_without_an_answer_is_an_error():
    """An empty signup answer can't give tokens."""
    with pytest.raises(ValueError, match="Unable to fetch id and refresh token"):
        burgerportaal._get_auth_token(FakeSession(_ok({})), **KWARGS)


def test_signup_without_a_refresh_token_is_an_error():
    """A signup answer without a refresh token can't give an id token."""
    with pytest.raises(KeyError, match="refreshToken"):
        burgerportaal._get_auth_token(FakeSession(_ok({"idToken": "x"})), **KWARGS)


def test_refresh_without_an_id_token_is_an_error():
    """The token answer must hold an id token."""
    with pytest.raises(KeyError, match="id_token"):
        burgerportaal._refresh_id_token(FakeSession(_ok({})), "ref", **KWARGS)


# --- helpers -----------------------------------------------------------------------


@pytest.mark.parametrize(
    "response",
    [
        FakeResponse(status_code=204, text="x"),
        FakeResponse(status_code=200, text=""),
        FakeResponse(status_code=200, text="   \n"),
        FakeResponse(None, text="null"),
    ],
)
def test_no_content_is_an_empty_list(response):
    """HTTP 204, a blank body and a null body all mean no data."""
    assert burgerportaal._json_or_empty(response) == []


def test_content_is_returned_as_is():
    """A normal answer is the list from the body."""
    assert burgerportaal._json_or_empty(_ok([{"a": 1}])) == [{"a": 1}]


@pytest.mark.parametrize(
    ("addresses", "suffix", "expected"),
    [
        ([], "", None),
        ([], "A", None),
        ([{"addressId": "a1"}, {"addressId": "a2"}], "", "a1"),
        (
            [
                {"addressId": "a1", "addition": None},
                {"addressId": "a2", "addition": "a"},
            ],
            "A",
            "a2",
        ),
        ([{"addressId": "a1", "addition": "B"}], "A", None),
        ([{"addressId": "a1", "addition": ""}], "A", None),
    ],
)
def test_select_address_id(addresses, suffix, expected):
    """Without a suffix the first address, with one the matching addition."""
    assert burgerportaal._select_address_id(addresses, suffix) == expected


def test_parse_splits_combined_types_and_sorts_by_date():
    """A fraction that stands for two types gives two pickups."""
    data = [
        {"collectionDate": "2026-11-20T00:00:00", "fraction": " Papier "},
        {"collectionDate": "2026-11-13T05:00:00+01:00", "fraction": "REST+PMD"},
    ]

    assert burgerportaal._parse_waste_data_raw(data) == [
        {"type": "pmd", "date": "2026-11-13"},
        {"type": "restafval", "date": "2026-11-13"},
        {"type": "papier", "date": "2026-11-20"},
    ]


@pytest.mark.parametrize(
    "item",
    [
        {"fraction": "GFT"},
        {"collectionDate": "", "fraction": "GFT"},
        {"collectionDate": "2026-11-13T00:00:00"},
        {"collectionDate": "2026-11-13T00:00:00", "fraction": ""},
    ],
)
def test_parse_skips_pickups_without_a_date_or_a_fraction(item):
    """Incomplete pickups are dropped."""
    assert burgerportaal._parse_waste_data_raw([item]) == []


# --- the flow and its caches -------------------------------------------------------


def test_flow_signs_in_looks_up_the_address_and_caches_it():
    """New user, token, address list, calendar. Both ids are remembered."""
    session = FakeSession(SIGNUP, TOKEN, ADDRESSES, CALENDAR)

    assert _run(session) == PICKUPS
    assert [call[0] for call in session.calls] == ["POST", "POST", "GET", "GET"]
    assert "/address?zipcode=1234AB&housenumber=5" in session.calls[2][1]
    assert session.calls[3][1].endswith("/address/addr-1/calendar")
    assert session.calls[3][2]["headers"]["authorization"] == "id-1"
    assert burgerportaal._AUTH_CACHE == {"refresh_token": "refresh-1"}
    assert list(burgerportaal._ADDRESS_ID_CACHE.values()) == ["addr-1"]


def test_flow_reuses_the_cached_refresh_token_and_address_id():
    """The second refresh signs in with the stored token and skips the lookup."""
    _run(FakeSession(SIGNUP, TOKEN, ADDRESSES, CALENDAR))
    session = FakeSession(TOKEN, CALENDAR)

    assert _run(session) == PICKUPS
    assert [call[0] for call in session.calls] == ["POST", "GET"]
    assert session.calls[0][2]["data"]["refresh_token"] == "refresh-1"


@pytest.mark.parametrize("stale", [_status(404), FakeResponse(status_code=204)])
def test_flow_looks_up_the_address_again_when_the_cached_id_is_stale(stale):
    """An error, or an empty calendar, drops the cached id."""
    _run(FakeSession(SIGNUP, TOKEN, ADDRESSES, CALENDAR))
    new_address = _ok([{"addressId": "addr-2", "addition": ""}])
    session = FakeSession(TOKEN, stale, new_address, CALENDAR)

    assert _run(session) == PICKUPS
    assert session.calls[-1][1].endswith("/address/addr-2/calendar")
    assert list(burgerportaal._ADDRESS_ID_CACHE.values()) == ["addr-2"]


def test_flow_with_a_given_id_token_makes_no_signup(caplog):
    """A caller that has a token needs no sign-in at all."""
    session = FakeSession(ADDRESSES, CALENDAR)

    assert _run(session, id_token="id-given") == PICKUPS
    assert [call[0] for call in session.calls] == ["GET", "GET"]


def test_flow_without_addresses_is_empty(caplog):
    """No address for the postal code and house number."""
    session = FakeSession(SIGNUP, TOKEN, FakeResponse(status_code=204))

    assert _run(session) == []
    assert "Unable to fetch address list" in caplog.text


def test_flow_without_the_requested_suffix_is_empty(caplog):
    """The addresses exist but none has this addition."""
    session = FakeSession(SIGNUP, TOKEN, ADDRESSES)

    with caplog.at_level(logging.WARNING):
        assert _run(session, suffix="b") == []
    assert "Address not found" in caplog.text
    assert burgerportaal._ADDRESS_ID_CACHE == {}


def test_flow_turns_a_request_error_into_a_value_error():
    """The error describes the failure, not the address."""
    session = FakeSession(SIGNUP, TOKEN, _status(503))

    with pytest.raises(ValueError, match=r"request failed \(HTTPError 503\)") as raised:
        _run(session)
    assert "1234AB" not in str(raised.value)


def test_flow_turns_unreadable_data_into_a_value_error():
    """A date that can't be read is reported as invalid data."""
    bad = _ok([{"collectionDate": "13-11-2026T00:00:00", "fraction": "GFT"}])
    session = FakeSession(SIGNUP, TOKEN, ADDRESSES, bad)

    with pytest.raises(ValueError, match="Invalid and/or no data received"):
        _run(session)


def test_flow_with_an_unknown_provider_is_refused():
    """The provider is checked before anything is requested."""
    session = FakeSession()

    with pytest.raises(ValueError, match="Invalid provider"):
        burgerportaal.get_waste_data_raw(
            "nonexistent", "1234AB", "5", "", session=session
        )
    assert session.calls == []


def test_a_connection_error_is_a_value_error():
    """A failure to connect is reported by its type."""
    session = FakeSession(requests.exceptions.ConnectionError("https://secret.example"))

    with pytest.raises(
        ValueError, match=r"request failed \(ConnectionError\)"
    ) as raised:
        _run(session)
    assert "secret.example" not in str(raised.value)
