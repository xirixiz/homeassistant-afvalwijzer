"""Tests for the RecycleApp collector: the id lookups, the cache and the parsing."""

import pytest
import requests

from custom_components.afvalwijzer.collector import recycleapp

from .fakes import FakeResponse


@pytest.fixture(autouse=True)
def _empty_cache(monkeypatch):
    """Each test starts without cached location ids."""
    monkeypatch.setattr(recycleapp, "_LOCATION_ID_CACHE", {})


class RoutedSession:
    """Session answering by the last part of the URL, remembering the requests."""

    def __init__(self, **routes):
        """Map zipcodes, streets and collections to a response or list of them."""
        self.routes = {key: list(_as_list(value)) for key, value in routes.items()}
        self.calls = []

    def get(self, url, **kwargs):
        """Answer a request, the last response of a route repeating."""
        name = url.rstrip("/").rsplit("/", 1)[-1]
        self.calls.append((name, kwargs))
        responses = self.routes[name]
        response = responses.pop(0) if len(responses) > 1 else responses[0]
        if isinstance(response, Exception):
            raise response
        return response

    def names(self):
        """Return which endpoints were asked, in order."""
        return [name for name, _ in self.calls]


def _as_list(value):
    return value if isinstance(value, list) else [value]


def _ok(payload):
    return FakeResponse(payload)


ZIPCODES = _ok({"items": [{"id": "zip-1"}]})
STREETS = _ok({"items": [{"id": "street-1", "name": "Teststraat"}]})


def _item(name="GFT", timestamp="2026-11-13T00:00:00.000Z", **extra):
    return {"timestamp": timestamp, "fraction": {"name": {"nl": name}}, **extra}


COLLECTIONS = _ok({"items": [_item("Papier", "2026-11-20T00:00:00.000Z"), _item()]})


def _run(session, street="Teststraat"):
    return recycleapp.get_waste_data_raw(
        "recycleapp",
        "1000",
        "5",
        "",
        street,
        session=session,
        timeout=(1, 1),
    )


def _http_error(status):
    return requests.exceptions.HTTPError(response=FakeResponse(status_code=status))


# --- provider and lookups ----------------------------------------------------------


def test_build_url_ends_with_a_slash():
    """The base URL always ends with exactly one slash."""
    assert recycleapp._build_url("recycleapp").endswith("/")
    assert not recycleapp._build_url("recycleapp").endswith("//")


def test_build_url_refuses_an_unknown_provider():
    """Only listed providers have an address."""
    with pytest.raises(ValueError, match="Invalid provider"):
        recycleapp._build_url("nonexistent")


def test_postcode_ids_skip_entries_without_an_id():
    """Every matching zipcode with an id is returned, as text."""
    session = RoutedSession(
        zipcodes=_ok({"items": [{"id": 1}, {"name": "no id"}, {"id": "b"}]})
    )

    assert recycleapp._fetch_postcode_ids(
        session, "https://x/", "1000", timeout=(1, 1), verify=True
    ) == ["1", "b"]


@pytest.mark.parametrize("payload", [{}, {"items": []}, {"items": [{}]}, None])
def test_postcode_lookup_without_a_result_is_an_error(payload):
    """No zipcode id means the postal code is unknown."""
    session = RoutedSession(zipcodes=_ok(payload))

    with pytest.raises(ValueError, match="postcode_id not found"):
        recycleapp._fetch_postcode_ids(
            session, "https://x/", "1000", timeout=(1, 1), verify=True
        )


@pytest.mark.parametrize(
    ("items", "expected"),
    [
        # an exact name beats the first result
        ([{"id": 1, "name": "Other"}, {"id": 2, "name": "Teststraat"}], "2"),
        # otherwise the first result is used
        ([{"id": 1, "name": "Other"}, {"id": 2, "name": "Another"}], "1"),
        ([{"id": 1, "name": "Teststraat"}], "1"),
        # an exact match without an id doesn't count
        ([{"name": "Teststraat"}, {"id": 3, "name": "Other"}], None),
        ([{"name": "Other"}], None),
        ([], None),
    ],
)
def test_street_id_prefers_the_exact_name(items, expected):
    """The street lookup returns the exact match, else the first street."""
    session = RoutedSession(streets=_ok({"items": items}))

    assert (
        recycleapp._fetch_street_id(
            session, "https://x/", "Teststraat", "zip-1", timeout=(1, 1), verify=True
        )
        == expected
    )


def test_street_is_looked_up_for_every_zipcode_until_found():
    """A zipcode without the street is skipped for the next one."""
    session = RoutedSession(
        zipcodes=_ok({"items": [{"id": "z1"}, {"id": "z2"}]}),
        streets=[_ok({"items": []}), _ok({"items": [{"id": "s2", "name": "Test"}]})],
    )

    assert recycleapp._fetch_postcode_and_street_id(
        session, "https://x/", "1000", "Test", timeout=(1, 1), verify=True
    ) == ("z2", "s2")
    assert [call[1]["params"]["zipcodes"] for call in session.calls[1:]] == [
        "z1",
        "z2",
    ]


def test_street_not_found_anywhere_is_an_error():
    """No zipcode has the street."""
    session = RoutedSession(zipcodes=ZIPCODES, streets=_ok({"items": []}))

    with pytest.raises(ValueError, match="street_id not found"):
        recycleapp._fetch_postcode_and_street_id(
            session, "https://x/", "1000", "Test", timeout=(1, 1), verify=True
        )


# --- parsing -----------------------------------------------------------------------


def test_parse_keeps_valid_pickups_sorted_by_date_then_type():
    """The result is ordered, whatever order the API used."""
    data = {
        "items": [
            _item("Papier", "2026-11-20T00:00:00.000Z"),
            _item("PMD", "2026-11-13T00:00:00.000Z"),
            _item("GFT", "2026-11-13T00:00:00.000Z"),
        ]
    }

    assert recycleapp._parse_waste_data_raw(data) == [
        {"type": "gft", "date": "2026-11-13"},
        {"type": "pmd", "date": "2026-11-13"},
        {"type": "papier", "date": "2026-11-20"},
    ]


@pytest.mark.parametrize(
    "item",
    [
        {"fraction": {"name": {"nl": "GFT"}}},
        _item(timestamp=""),
        {"timestamp": "2026-11-13T00:00:00.000Z"},
        {"timestamp": "2026-11-13T00:00:00.000Z", "fraction": {"name": {}}},
        {"timestamp": "2026-11-13T00:00:00.000Z", "fraction": {"name": {"nl": ""}}},
        _item(exception={"replacedBy": {"id": "other"}}),
    ],
)
def test_parse_skips_pickups_it_cannot_use(item):
    """A pickup without a date or a name, or one that was replaced, is dropped."""
    assert recycleapp._parse_waste_data_raw({"items": [item]}) == []


def test_parse_keeps_a_pickup_with_an_exception_that_replaces_nothing():
    """An exception record alone doesn't hide the pickup."""
    data = {"items": [_item(exception={"reason": "holiday"})]}

    assert recycleapp._parse_waste_data_raw(data) == [
        {"type": "gft", "date": "2026-11-13"}
    ]


def test_parse_of_nothing_is_empty():
    """No items, or no key, gives nothing."""
    assert recycleapp._parse_waste_data_raw({}) == []
    assert recycleapp._parse_waste_data_raw({"items": None}) == []


# --- the flow and the cache --------------------------------------------------------


def test_flow_looks_up_the_ids_and_remembers_them():
    """First refresh: zipcode, street, collections. The ids are cached."""
    session = RoutedSession(zipcodes=ZIPCODES, streets=STREETS, collections=COLLECTIONS)

    assert _run(session) == [
        {"type": "gft", "date": "2026-11-13"},
        {"type": "papier", "date": "2026-11-20"},
    ]
    assert session.names() == ["zipcodes", "streets", "collections"]
    collections = session.calls[-1][1]["params"]
    assert collections["zipcodeId"] == "zip-1"
    assert collections["streetId"] == "street-1"
    assert collections["houseNumber"] == "5"
    assert recycleapp._LOCATION_ID_CACHE == {
        ("1000", "Teststraat"): ("zip-1", "street-1")
    }


def test_flow_with_cached_ids_needs_one_request():
    """Second refresh: only the collections are asked."""
    recycleapp._LOCATION_ID_CACHE[("1000", "Teststraat")] = ("zip-1", "street-1")
    session = RoutedSession(collections=COLLECTIONS)

    assert len(_run(session)) == 2
    assert session.names() == ["collections"]


@pytest.mark.parametrize("status", [400, 404])
def test_flow_looks_up_again_when_the_cached_ids_are_rejected(status):
    """Stale ids (400 or 404) are dropped and looked up again."""
    recycleapp._LOCATION_ID_CACHE[("1000", "Teststraat")] = ("old-zip", "old-street")
    session = RoutedSession(
        zipcodes=ZIPCODES,
        streets=STREETS,
        collections=[_http_error(status), COLLECTIONS],
    )

    assert len(_run(session)) == 2
    assert session.names() == ["collections", "zipcodes", "streets", "collections"]
    assert recycleapp._LOCATION_ID_CACHE[("1000", "Teststraat")] == (
        "zip-1",
        "street-1",
    )


@pytest.mark.parametrize("status", [500, 503])
def test_flow_keeps_the_cache_when_the_server_fails(status):
    """A server error is no reason to forget the ids."""
    recycleapp._LOCATION_ID_CACHE[("1000", "Teststraat")] = ("zip-1", "street-1")
    session = RoutedSession(collections=_http_error(status))

    with pytest.raises(ValueError, match=rf"request failed \(HTTPError {status}\)"):
        _run(session)
    assert ("1000", "Teststraat") in recycleapp._LOCATION_ID_CACHE


def test_flow_without_a_street_name_is_empty(caplog):
    """The street name is required; without it nothing is requested."""
    session = RoutedSession()

    assert _run(session, street=None) == []
    assert "street_name is required" in caplog.text
    assert session.calls == []


def test_flow_with_an_empty_answer_is_empty(caplog):
    """An empty collections answer gives no pickups."""
    session = RoutedSession(zipcodes=ZIPCODES, streets=STREETS, collections=_ok({}))

    assert _run(session) == []
    assert "No Waste data found" in caplog.text


def test_flow_turns_a_request_error_into_a_value_error():
    """The error describes the failure, not the address."""
    session = RoutedSession(zipcodes=_http_error(503))

    with pytest.raises(ValueError, match=r"request failed \(HTTPError 503\)") as raised:
        _run(session)
    assert "1000" not in str(raised.value)


@pytest.mark.parametrize(
    "streets",
    [_ok({"items": []}), _ok({"items": [{"id": "s", "name": "Teststraat"}]})],
)
def test_flow_turns_unexpected_data_into_a_value_error(streets):
    """A missing street, or a date that can't be read, is invalid data."""
    bad_date = _ok({"items": [_item(timestamp="13-11-2026")]})
    session = RoutedSession(zipcodes=ZIPCODES, streets=streets, collections=bad_date)

    with pytest.raises(ValueError, match="Invalid and/or no data received"):
        _run(session)


def test_flow_refuses_an_unknown_provider():
    """An unknown provider is reported as invalid data."""
    with pytest.raises(ValueError, match="Invalid and/or no data received"):
        recycleapp.get_waste_data_raw(
            "nonexistent", "1000", "5", "", "Teststraat", session=RoutedSession()
        )
