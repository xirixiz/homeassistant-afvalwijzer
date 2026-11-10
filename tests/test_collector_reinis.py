"""Tests for the Reinis collector (Scoop resident website + iCal feed)."""

import json

import pytest
import requests

from custom_components.afvalwijzer.collector import reinis

ACTION_ID = "40e9e910c92ad2df3a6e7323c73dc0a3658eb0fb12"
ADDRESS_ID = "8e75bc43-2774-4789-b474-833d96032877"
FEED_URL = (
    f"https://website.scoopresident.com/api/proxy/pickups/ical/{ADDRESS_ID}?token=t1"
)

POSTCODE_HTML = (
    '<script src="/_next/static/chunks/0common.js?dpl=x" async></script>'
    '<script src="/_next/static/chunks/1page.js?dpl=x" async></script>'
)
# Shaped like the minified Next.js chunk that defines the server action.
PAGE_CHUNK = (
    'let u=(0,n.createServerReference)("'
    + ACTION_ID
    + '",r.callServer,void 0,r.findSourceMapURL,"ensureAnonSessionAction");'
)
ICAL = (
    "BEGIN:VCALENDAR\r\n"
    "PRODID:-//Reinis//Afvalkalender//NL\r\n"
    "BEGIN:VEVENT\r\n"
    "UID:evreka-2026-11-13-gft-x@website.scoo\r\n president.com\r\n"
    "DTSTART;VALUE=DATE:20261113\r\n"
    "SUMMARY:GFT inzameling\r\n"
    "END:VEVENT\r\n"
    "BEGIN:VEVENT\r\n"
    "DTSTART;VALUE=DATE:20261120\r\n"
    "SUMMARY:PMD inzameling\r\n"
    "END:VEVENT\r\n"
    "BEGIN:VEVENT\r\n"
    "DTSTART;VALUE=DATE:20261127\r\n"
    "SUMMARY:OPK / Oud papier inzameling\r\n"
    "END:VEVENT\r\n"
    "END:VCALENDAR\r\n"
)


class FakeResponse:
    """Minimal requests.Response stand-in."""

    def __init__(self, text="", status_code=200, payload=None):
        """Store the body and status code."""
        self.text = text
        self.status_code = status_code
        self._payload = payload

    @property
    def ok(self):
        """Mirror requests.Response.ok."""
        return self.status_code < 400

    def json(self):
        """Return the payload."""
        return self._payload

    def raise_for_status(self):
        """Raise HTTPError for error statuses."""
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)


class FakeSession:
    """Session answering by URL fragment; the address POST sets the cookie."""

    def __init__(self, routes, *, address_found=True):
        """Store the routes."""
        self.routes = routes
        self.address_found = address_found
        self.cookies = requests.cookies.RequestsCookieJar()
        self.calls = []
        self.posts = []

    def _answer(self, url):
        for fragment, response in self.routes:
            if fragment in url:
                return response.pop(0) if isinstance(response, list) else response
        raise AssertionError(f"unexpected URL {url}")

    def get(self, url, params=None, **_kwargs):
        """Answer a GET."""
        self.calls.append(("GET", url, params))
        return self._answer(url)

    def post(self, url, data=None, headers=None, **_kwargs):
        """Answer the address server action."""
        self.calls.append(("POST", url, None))
        self.posts.append((json.loads(data), headers))
        if self.address_found:
            self.cookies.set(reinis._ADDRESS_ID_COOKIE, ADDRESS_ID)
        return FakeResponse("0:{}")

    def count(self, fragment):
        """Return how many requests contained the fragment."""
        return sum(fragment in url for _, url, _ in self.calls)


def _routes(feed=None):
    return [
        ("/postcode", FakeResponse(POSTCODE_HTML)),
        ("/chunks/0common.js", FakeResponse("console.log(1)")),
        ("/chunks/1page.js", FakeResponse(PAGE_CHUNK)),
        (
            "/ical-subscription",
            FakeResponse(payload={"ok": True, "data": {"url": FEED_URL}}),
        ),
        ("/pickups/ical/", feed if feed is not None else FakeResponse(ICAL)),
    ]


@pytest.fixture(autouse=True)
def _clear_cache():
    reinis._ICAL_URL_CACHE.clear()
    yield
    reinis._ICAL_URL_CACHE.clear()


def test_reinis_reads_the_ical_feed():
    """The website flow yields the feed, mapped to the usual waste types."""
    session = FakeSession(_routes())

    result = reinis.get_waste_data_raw("reinis", "3232 pw", "19", "", session=session)

    assert result == [
        {"date": "2026-11-13", "type": "gft"},
        {"date": "2026-11-20", "type": "pmd"},
        {"date": "2026-11-27", "type": "papier"},
    ]
    payload, headers = session.posts[0]
    assert payload == [{"postcode": "3232PW", "huisnummer": "19", "toev": "$undefined"}]
    assert headers["Next-Action"] == ACTION_ID
    assert (
        "GET",
        "https://reinis.nl/api/proxy/pickups/ical-subscription",
        {"addressId": ADDRESS_ID},
    ) in session.calls


def test_reinis_sends_the_suffix():
    """A house number suffix is passed as toevoeging."""
    session = FakeSession(_routes())

    reinis.get_waste_data_raw("reinis", "3232PW", "19", "a", session=session)

    assert session.posts[0][0][0]["toev"] == "a"


def test_reinis_reuses_the_cached_feed_url():
    """A second refresh fetches only the feed."""
    reinis.get_waste_data_raw(
        "reinis", "3232PW", "19", "", session=FakeSession(_routes())
    )
    session = FakeSession(_routes())

    result = reinis.get_waste_data_raw("reinis", "3232PW", "19", "", session=session)

    assert len(result) == 3
    assert session.count("/postcode") == 0
    assert session.count("/pickups/ical/") == 1


def test_reinis_looks_up_again_when_the_cached_feed_fails():
    """A rejected feed URL triggers a fresh lookup instead of an error."""
    reinis._ICAL_URL_CACHE[("3232PW", "19", "")] = (
        "https://website.scoopresident.com/old"
    )
    session = FakeSession([("/old", FakeResponse(status_code=401)), *_routes()])

    result = reinis.get_waste_data_raw("reinis", "3232PW", "19", "", session=session)

    assert len(result) == 3
    assert session.count("/postcode") == 2  # page GET + action POST
    assert reinis._ICAL_URL_CACHE[("3232PW", "19", "")] == FEED_URL


def test_reinis_unknown_address_returns_empty():
    """No address cookie means the address is unknown to Reinis."""
    session = FakeSession(_routes(), address_found=False)

    assert (
        reinis.get_waste_data_raw("reinis", "3232PW", "99999", "", session=session)
        == []
    )
    assert reinis._ICAL_URL_CACHE == {}


def test_reinis_missing_action_id_raises():
    """A website change that hides the action id is reported, not swallowed."""
    routes = _routes()
    routes[2] = ("/chunks/1page.js", FakeResponse("nothing here"))

    with pytest.raises(ValueError):
        reinis.get_waste_data_raw(
            "reinis", "3232PW", "19", "", session=FakeSession(routes)
        )


def test_reinis_non_ical_feed_raises():
    """An HTML error page instead of a feed is treated as invalid data."""
    session = FakeSession(_routes(feed=FakeResponse("<!DOCTYPE html>")))

    with pytest.raises(ValueError):
        reinis.get_waste_data_raw("reinis", "3232PW", "19", "", session=session)
    assert reinis._ICAL_URL_CACHE == {}


def test_reinis_address_without_kerbside_pickups(caplog):
    """An empty feed (underground containers) yields no data and a warning."""
    empty = (
        "BEGIN:VCALENDAR\r\nX-WR-CALDESC:Geen vaste ophaaldagen\r\nEND:VCALENDAR\r\n"
    )
    session = FakeSession(_routes(feed=FakeResponse(empty)))

    assert (
        reinis.get_waste_data_raw("reinis", "3232GG", "10", "", session=session) == []
    )
    assert "no kerbside pickups" in caplog.text
