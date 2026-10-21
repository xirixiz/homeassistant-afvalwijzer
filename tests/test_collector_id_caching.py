"""Tests that Burgerportaal and RecycleApp reuse the ids they looked up."""

import pytest
import requests

from custom_components.afvalwijzer.collector import burgerportaal, recycleapp


class FakeResponse:
    """Minimal requests.Response stand-in."""

    def __init__(self, payload, status_code=200):
        """Store the payload and status code."""
        self._payload = payload
        self.status_code = status_code
        self.text = "x"

    def json(self):
        """Return the payload."""
        return self._payload

    def raise_for_status(self):
        """Raise HTTPError for error statuses."""
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)


class FakeSession:
    """Session answering by URL fragment; a list means one response per call."""

    def __init__(self, routes):
        """Store the routes."""
        self.routes = routes
        self.urls = []

    def _answer(self, url):
        self.urls.append(url)
        for fragment, response in self.routes:
            if fragment in url:
                return response.pop(0) if isinstance(response, list) else response
        raise AssertionError(f"unexpected URL {url}")

    def get(self, url, **_kwargs):
        """Answer a GET."""
        return self._answer(url)

    def post(self, url, **_kwargs):
        """Answer a POST."""
        return self._answer(url)

    def count(self, fragment):
        """Return how many requests contained the fragment."""
        return sum(fragment in url for url in self.urls)


@pytest.fixture(autouse=True)
def _clear_caches():
    for cache in (
        burgerportaal._AUTH_CACHE,
        burgerportaal._ADDRESS_ID_CACHE,
        recycleapp._LOCATION_ID_CACHE,
    ):
        cache.clear()
    yield
    for cache in (
        burgerportaal._AUTH_CACHE,
        burgerportaal._ADDRESS_ID_CACHE,
        recycleapp._LOCATION_ID_CACHE,
    ):
        cache.clear()


def _burgerportaal_routes():
    return [
        ("signupNewUser", FakeResponse({"refreshToken": "ref"})),
        ("securetoken", FakeResponse({"id_token": "id"})),
        ("/address?", FakeResponse([{"addressId": "a1", "addition": None}])),
        (
            "/calendar",
            FakeResponse(
                [{"collectionDate": "2026-10-05T00:00:00", "fraction": "gft"}]
            ),
        ),
    ]


def test_burgerportaal_signs_up_and_looks_up_address_once():
    """A second refresh reuses the refresh token and the address id."""
    session = FakeSession(_burgerportaal_routes())

    for _ in range(2):
        result = burgerportaal.get_waste_data_raw(
            "assen", "1234AB", "1", "", session=session
        )
        assert result == [{"type": "gft", "date": "2026-10-05"}]

    assert session.count("signupNewUser") == 1
    assert session.count("/address?") == 1
    assert session.count("/calendar") == 2


def test_burgerportaal_looks_up_address_again_when_cached_id_is_rejected():
    """A rejected cached address id is replaced by a fresh lookup."""
    burgerportaal._ADDRESS_ID_CACHE[("138204213565303512", "1234AB", "1", "")] = "stale"
    session = FakeSession(
        [
            ("signupNewUser", FakeResponse({"refreshToken": "ref"})),
            ("securetoken", FakeResponse({"id_token": "id"})),
            ("/address?", FakeResponse([{"addressId": "a1", "addition": None}])),
            (
                "/calendar",
                [
                    FakeResponse({}, status_code=404),
                    FakeResponse(
                        [{"collectionDate": "2026-10-05T00:00:00", "fraction": "gft"}]
                    ),
                ],
            ),
        ]
    )

    result = burgerportaal.get_waste_data_raw(
        "assen", "1234AB", "1", "", session=session
    )

    assert result == [{"type": "gft", "date": "2026-10-05"}]
    assert session.count("/address?") == 1
    assert (
        burgerportaal._ADDRESS_ID_CACHE[("138204213565303512", "1234AB", "1", "")]
        == "a1"
    )


def _recycleapp_routes(collections):
    return [
        ("/zipcodes", FakeResponse({"items": [{"id": "z1"}]})),
        ("/streets", FakeResponse({"items": [{"id": "s1", "name": "Straat"}]})),
        ("/collections", collections),
    ]


def test_recycleapp_looks_up_location_once():
    """A second refresh goes straight to the collections endpoint."""
    collections = FakeResponse(
        {
            "items": [
                {
                    "timestamp": "2026-10-05T00:00:00.000Z",
                    "fraction": {"name": {"nl": "GFT"}},
                }
            ]
        }
    )
    session = FakeSession(_recycleapp_routes(collections))

    for _ in range(2):
        result = recycleapp.get_waste_data_raw(
            "recycleapp", "9000", "1", "", "Straat", session=session
        )
        assert result == [{"type": "gft", "date": "2026-10-05"}]

    assert session.count("/zipcodes") == 1
    assert session.count("/streets") == 1
    assert session.count("/collections") == 2


def test_recycleapp_looks_up_location_again_on_404():
    """A 404 on the collections endpoint clears the cached ids and retries."""
    recycleapp._LOCATION_ID_CACHE[("9000", "Straat")] = ("old-z", "old-s")
    ok = FakeResponse(
        {
            "items": [
                {
                    "timestamp": "2026-10-05T00:00:00.000Z",
                    "fraction": {"name": {"nl": "GFT"}},
                }
            ]
        }
    )
    session = FakeSession(_recycleapp_routes([FakeResponse({}, status_code=404), ok]))

    result = recycleapp.get_waste_data_raw(
        "recycleapp", "9000", "1", "", "Straat", session=session
    )

    assert result == [{"type": "gft", "date": "2026-10-05"}]
    assert recycleapp._LOCATION_ID_CACHE[("9000", "Straat")] == ("z1", "s1")
