"""Tests for the RD4 app notifications (address-only session)."""

from datetime import UTC, datetime, timedelta

import pytest
import requests

from custom_components.afvalwijzer.collector import rd4
from custom_components.afvalwijzer.collector.main_collector import MainCollector

API = "https://data.rd4.nl/api/v2"
TOKEN = "session-token"
RECENT = (datetime.now(UTC) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ")


class FakeResponse:
    """Minimal requests.Response stand-in."""

    def __init__(self, payload=None, status_code=200):
        """Store the payload and status code."""
        self._payload = payload
        self.status_code = status_code

    def json(self):
        """Return the payload."""
        return self._payload

    def raise_for_status(self):
        """Raise HTTPError for error statuses."""
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)


def _page(*items):
    return FakeResponse(
        {
            "page": None,
            "limit": 50,
            "items": list(items),
            "nextKey": None,
            "total": len(items),
        }
    )


PERSONAL = {
    "id": "00000000-0000-4000-8000-000000000001",
    "title": "Aangepaste ophaaldag",
    "description": "<p>Jouw <b>GFT</b>-container wordt deze week op vrijdag &amp; niet op donderdag geleegd.</p>",
    "date": RECENT,
    "read": False,
    "newsId": "1",
    "type": "personal-news",
}


class FakeSession:
    """Session answering the app login, terms and notifications requests."""

    def __init__(self, notifications=None, *, token=TOKEN, session_status=201):
        """Store the answers; notifications may be a list of answers in order."""
        self.token = token
        self.session_status = session_status
        self.notifications = (
            notifications if notifications is not None else [_page(PERSONAL)]
        )
        self.calls = []

    def post(self, url, json=None, headers=None, **_kwargs):
        """Answer the login."""
        self.calls.append(("POST", url, json, headers))
        payload = {"authToken": self.token, "authLevel": 1} if self.token else {}
        return FakeResponse(payload, self.session_status)

    def put(self, url, headers=None, **_kwargs):
        """Answer the terms agreement."""
        self.calls.append(("PUT", url, None, headers))
        return FakeResponse(status_code=204)

    def get(self, url, params=None, headers=None, **_kwargs):
        """Answer the current terms or the notifications."""
        self.calls.append(("GET", url, params, headers))
        if url == f"{API}/tos/current":
            return FakeResponse({"id": 1, "contents": "<p>Algemene voorwaarden</p>"})
        if url == f"{API}/notifications":
            if isinstance(self.notifications, list):
                return self.notifications.pop(0)
            return self.notifications
        raise AssertionError(f"unexpected URL {url}")

    def urls(self):
        """Return the requests as 'METHOD path'."""
        return [f"{method} {url.removeprefix(API)}" for method, url, _, _ in self.calls]


@pytest.fixture(autouse=True)
def _clear_cache():
    rd4._TOKEN_CACHE.clear()
    yield
    rd4._TOKEN_CACHE.clear()


def _run(session, house_number="32", suffix=""):
    return rd4.get_notification_data_raw(
        "rd4", "6417 at", house_number, suffix, session=session
    )


def test_new_session_accepts_terms_and_returns_messages():
    """Login, accept the terms, read the messages, cleaned up."""
    session = FakeSession()

    result = _run(session)

    assert result == [
        {
            "id": PERSONAL["id"],
            "type": "personal-news",
            "title": "Aangepaste ophaaldag",
            "content": "Jouw GFT-container wordt deze week op vrijdag & niet op donderdag geleegd.",
            "date": RECENT,
            "dismissable": False,
        }
    ]
    assert session.urls() == [
        "POST /auth/session",
        "GET /tos/current",
        "PUT /tos/1/agree",
        "GET /notifications",
    ]
    _, _, body, headers = session.calls[0]
    assert body == {
        "type": "waste-card",
        "postalCode": "6417AT",
        "houseNr": 32,
        "houseNrExt": "",
        "wasteCardNr": None,
    }
    assert headers["X-Rd4-Client"] == "android/app.rd4.nl/4.6.2"
    assert "Authorization" not in headers
    _, _, params, headers = session.calls[-1]
    assert params["types[]"] == ["personal-news", "news"]
    assert headers["Authorization"] == f"Bearer {TOKEN}"


def test_cached_session_only_reads_notifications():
    """A second refresh reuses the session token."""
    _run(FakeSession())
    session = FakeSession()

    assert len(_run(session)) == 1
    assert session.urls() == ["GET /notifications"]


@pytest.mark.parametrize("status", [401, 403])
def test_rejected_session_starts_a_new_one(status):
    """An expired token, or new terms to accept, triggers a fresh session."""
    _run(FakeSession())
    rejected = FakeResponse(
        {"code": 3, "message": "The Terms of Service haven't been accepted"}, status
    )
    session = FakeSession([rejected, _page(PERSONAL)])

    assert len(_run(session)) == 1
    assert session.urls() == [
        "GET /notifications",
        "POST /auth/session",
        "GET /tos/current",
        "PUT /tos/1/agree",
        "GET /notifications",
    ]


def test_server_error_keeps_the_cached_session(caplog):
    """A 5xx doesn't throw the session away and logs no details."""
    _run(FakeSession())
    session = FakeSession(FakeResponse({"code": 0}, 503))

    assert _run(session) == []
    assert session.urls() == ["GET /notifications"]
    assert rd4._TOKEN_CACHE
    assert "HTTPError" in caplog.text
    assert TOKEN not in caplog.text


def test_suffix_is_sent_as_house_number_extension():
    """The suffix becomes houseNrExt."""
    session = FakeSession()

    _run(session, suffix="a")

    assert session.calls[0][2]["houseNrExt"] == "A"


def test_other_types_and_empty_items_are_skipped():
    """Calendar reminders, tickets and empty messages are left out."""
    reminder = {**PERSONAL, "type": "waste-calendar", "pickUpDate": "2026-11-12"}
    ticket = {**PERSONAL, "type": "ticket", "ticketId": "1"}
    empty = {**PERSONAL, "id": "e", "title": " ", "description": "<p></p>"}
    news = {
        **PERSONAL,
        "id": "n",
        "type": "news",
        "title": "Nieuws",
        "description": "Algemeen",
    }
    session = FakeSession(_page(reminder, ticket, empty, news))

    assert [item["id"] for item in _run(session)] == ["n"]


def test_messages_older_than_30_days_are_left_out():
    """RD4 never expires messages, so old ones are dropped by date."""
    now = datetime(2026, 11, 11, 12, 0, tzinfo=UTC)
    items = [
        {**PERSONAL, "id": "new", "date": "2026-11-11T11:32:27Z"},
        {**PERSONAL, "id": "edge", "date": "2026-10-12T12:00:00Z"},
        {**PERSONAL, "id": "old", "date": "2026-07-31T08:59:05Z"},
        {**PERSONAL, "id": "naive", "date": "2026-11-01T08:00:00"},
        {**PERSONAL, "id": "undated", "date": None},
    ]

    result = rd4._parse_notifications(items, now)

    assert [item["id"] for item in result] == ["new", "edge", "naive", "undated"]


def test_no_token_means_no_notifications():
    """Without a session token nothing else is requested."""
    session = FakeSession(token=None)

    assert _run(session) == []
    assert session.urls() == ["POST /auth/session"]


def test_unknown_address_returns_nothing(caplog):
    """A rejected login returns nothing and is logged by type only."""
    session = FakeSession(session_status=404)

    assert _run(session) == []
    assert "HTTPError" in caplog.text
    assert rd4._TOKEN_CACHE == {}


def test_non_numeric_house_number_skips_notifications():
    """The app API wants a numeric house number."""
    session = FakeSession()

    assert _run(session, house_number="32a") == []
    assert session.calls == []


def test_unknown_provider_is_rejected():
    """Only RD4 is accepted."""
    with pytest.raises(ValueError):
        rd4.get_notification_data_raw("rova", "6417AT", "32", session=FakeSession())


def test_rd4_advertises_notifications():
    """The notifications sensor is created for RD4."""
    assert MainCollector.provider_supports_notifications("rd4")
