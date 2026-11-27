"""Tests for the Ximmio collector: provider lookup, the IPv4/IPv6 retry and the flow."""

import socket

import pytest
import requests
from urllib3.util import connection as urllib3_connection

from custom_components.afvalwijzer.collector import ximmio

from .fakes import FakeResponse, FakeSession

ADDRESS = {"dataList": [{"UniqueId": "abc-123", "Community": "Teststad"}]}
CALENDAR = {
    "dataList": [
        {"_pickupTypeText": "GREEN", "pickupDates": ["2026-11-03T00:00:00"]},
        {"_pickupTypeText": "PAPER", "pickupDates": ["2026-11-10T00:00:00"]},
    ]
}


def _run(session, suffix="", provider="avalex"):
    return ximmio.get_waste_data_raw(
        provider, "1234AB", "5", suffix, session=session, timeout=(1, 1)
    )


# --- provider lookup ---------------------------------------------------------------


def test_build_url_of_a_provider_with_its_own_host():
    """Providers listed with a host use it."""
    assert ximmio._build_url("avalex") == "https://wasteprod2api.ximmio.com"


def test_build_url_falls_back_to_the_generic_host():
    """A provider with only a company code uses the generic Ximmio host."""
    assert ximmio._build_url("almere") == "https://wasteapi.ximmio.com"


def test_build_url_refuses_a_provider_without_any_host(monkeypatch):
    """A known company code without a host, and no generic host, is rejected."""
    monkeypatch.setattr(ximmio, "SENSOR_COLLECTORS_XIMMIO", {})

    with pytest.raises(ValueError, match="Invalid provider"):
        ximmio._build_url("almere")


def test_build_url_refuses_an_unknown_provider():
    """A provider without a company code is rejected."""
    with pytest.raises(ValueError, match="Invalid provider"):
        ximmio._build_url("nonexistent")


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        ({"dataList": [1]}, [1]),
        ({"datalist": [2]}, [2]),
        ({"dataList": [1], "datalist": [2]}, [1]),
        ({"dataList": "x", "datalist": [2]}, [2]),
        ({"dataList": None}, []),
        ({}, []),
    ],
)
def test_get_data_list_accepts_either_spelling(response, expected):
    """The list may sit under dataList or datalist; anything else is empty."""
    assert ximmio._get_data_list(response) == expected


# --- IPv4 first, then IPv6 ---------------------------------------------------------


class _FamilySession:
    """Session recording which address family each POST was allowed to use."""

    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.families = []

    def post(self, url, **_kwargs):
        self.families.append(urllib3_connection.allowed_gai_family())
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def test_post_uses_ipv4_first():
    """When IPv4 works there is a single request."""
    original = urllib3_connection.allowed_gai_family
    response = FakeResponse({})
    session = _FamilySession(response)

    assert ximmio._post_ipv4_then_ipv6(session, url="https://x") is response
    assert session.families == [socket.AF_INET]
    assert urllib3_connection.allowed_gai_family is original


def test_post_retries_over_ipv6_when_ipv4_fails():
    """A connection error over IPv4 is retried over IPv6."""
    original = urllib3_connection.allowed_gai_family
    response = FakeResponse({})
    session = _FamilySession(requests.exceptions.ConnectionError("down"), response)

    assert ximmio._post_ipv4_then_ipv6(session, url="https://x") is response
    assert session.families == [socket.AF_INET, socket.AF_INET6]
    assert urllib3_connection.allowed_gai_family is original


def test_post_gives_up_when_both_families_fail():
    """The error names the IPv4 failure and not the request's address."""
    original = urllib3_connection.allowed_gai_family
    session = _FamilySession(
        requests.exceptions.ConnectionError("https://secret.example/1234AB"),
        requests.exceptions.Timeout("slow"),
    )

    with pytest.raises(
        ValueError, match=r"\(IPv4 then IPv6\): ConnectionError"
    ) as raised:
        ximmio._post_ipv4_then_ipv6(session, url="https://x")

    assert "secret.example" not in str(raised.value)
    assert urllib3_connection.allowed_gai_family is original


# --- requests ----------------------------------------------------------------------


def test_address_request_sends_the_suffix_only_when_there_is_one():
    """HouseLetter is part of the request for an address with a suffix."""
    session = FakeSession(FakeResponse(ADDRESS))
    ximmio._fetch_address_data(
        session, "https://x", "avalex", "1234AB", "5", suffix="A", timeout=(1, 1)
    )
    ximmio._fetch_address_data(
        session, "https://x", "avalex", "1234AB", "5", suffix="", timeout=(1, 1)
    )

    with_suffix, without = (call[2]["data"] for call in session.calls)
    assert with_suffix["HouseLetter"] == "A"
    assert "HouseLetter" not in without
    assert with_suffix["postCode"] == "1234AB"
    assert with_suffix["houseNumber"] == "5"
    assert session.urls() == ["https://x/api/FetchAdress"] * 2


def test_an_empty_body_is_an_empty_answer():
    """A body of null is treated as no data."""
    session = FakeSession(FakeResponse(None))

    assert (
        ximmio._fetch_address_data(
            session, "https://x", "avalex", "1234AB", "5", suffix="", timeout=(1, 1)
        )
        == {}
    )


# --- dates and parsing -------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("2026-10-05T00:00:00", "2026-10-05"),
        ("2026-10-05", "2026-10-05"),
        ("2026-10-05T10:30:00Z", "2026-10-05"),
        ("2026-10-05T10:30:00.123456", "2026-10-05"),
        ("", None),
        ("garbage", None),
    ],
)
def test_parse_ximmio_date(value, expected):
    """The date is cut from the formats Ximmio is known to send."""
    assert ximmio._parse_ximmio_date(value) == expected


def test_parse_skips_items_it_cannot_use():
    """Non-dicts, items without dates and streams without a name are ignored."""
    data = {
        "dataList": [
            "not a dict",
            {"_pickupTypeText": "GREEN", "pickupDates": []},
            {"_pickupTypeText": "GREEN"},
            {"_pickupTypeText": "", "pickupDates": ["2026-10-05T00:00:00"]},
            {"_pickupTypeText": None, "pickupDates": ["2026-10-05T00:00:00"]},
            {"_pickupTypeText": "PAPER", "pickupDates": ["2026-10-12T00:00:00"]},
        ]
    }

    assert ximmio._parse_waste_data_raw(data) == [
        {"type": "papier", "date": "2026-10-12"}
    ]


def test_parse_maps_plain_plastic_to_pmd_for_the_given_postal_code():
    """The postal code is handed on to the waste type mapping."""
    data = {
        "dataList": [
            {"_pickupTypeText": "PACKAGES", "pickupDates": ["2026-10-05T00:00:00"]}
        ]
    }

    assert ximmio._parse_waste_data_raw(data, "1234AB") == [
        {"type": "pmd", "date": "2026-10-05"}
    ]


# --- the whole flow ----------------------------------------------------------------


def test_flow_returns_the_pickups():
    """Address lookup, then calendar, then parsing."""
    session = FakeSession(FakeResponse(ADDRESS), FakeResponse(CALENDAR))

    assert _run(session, suffix=" a ") == [
        {"type": "gft", "date": "2026-11-03"},
        {"type": "papier", "date": "2026-11-10"},
    ]
    address_request, calendar_request = (call[2]["data"] for call in session.calls)
    assert address_request["HouseLetter"] == "A"
    assert calendar_request["uniqueAddressID"] == "abc-123"
    assert calendar_request["community"] == "Teststad"
    assert calendar_request["companyCode"] == address_request["companyCode"]
    assert session.urls() == [
        "https://wasteprod2api.ximmio.com/api/FetchAdress",
        "https://wasteprod2api.ximmio.com/api/GetCalendar",
    ]


@pytest.mark.parametrize(
    ("address", "message"),
    [
        ({}, "Address not found!"),
        ({"dataList": []}, "Address not found!"),
        ({"dataList": [{"Community": "Teststad"}]}, "missing UniqueId"),
        ({"dataList": ["not a dict"]}, "missing UniqueId"),
    ],
)
def test_flow_without_a_usable_address_is_empty(address, message, caplog):
    """An unknown address is logged and gives no pickups."""
    session = FakeSession(FakeResponse(address))

    assert _run(session) == []
    assert message in caplog.text
    assert len(session.calls) == 1


def test_flow_without_a_calendar_is_empty(caplog):
    """An empty calendar answer is logged and gives no pickups."""
    session = FakeSession(FakeResponse(ADDRESS), FakeResponse({}))

    assert _run(session) == []
    assert "Could not retrieve trash schedule" in caplog.text


def test_flow_turns_a_request_error_into_a_value_error():
    """A failing request is reported by the type of the error."""
    session = FakeSession(FakeResponse({}, status_code=503))

    with pytest.raises(ValueError, match="XIMMIO request failed"):
        _run(session)


def test_flow_turns_bad_json_into_a_value_error():
    """A body that is not JSON is reported as a request failure."""
    session = FakeSession(FakeResponse(json_error=True))

    with pytest.raises(ValueError, match="XIMMIO request failed"):
        _run(session)


def test_flow_refuses_an_unknown_provider():
    """An unknown provider is reported as invalid data."""
    with pytest.raises(ValueError, match="Invalid and/or no data received"):
        _run(FakeSession(FakeResponse({})), provider="nonexistent")


def test_flow_turns_unexpected_data_into_a_value_error():
    """A calendar that can't be read is reported as invalid data."""
    calendar = {"dataList": [{"_pickupTypeText": "GREEN", "pickupDates": [5]}]}
    session = FakeSession(FakeResponse(ADDRESS), FakeResponse(calendar))

    with pytest.raises(ValueError, match="Invalid and/or no data received"):
        _run(session)
