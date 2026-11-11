"""Tests for the RD4 app notifications (address-only session)."""

import pytest
import requests

from custom_components.afvalwijzer.collector import rd4
from custom_components.afvalwijzer.collector.main_collector import MainCollector

TOKEN = "session-token"


class FakeResponse:
    """Minimal requests.Response stand-in."""

    def __init__(self, payload, status_code=200):
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


class FakeSession:
    """Session answering the app login and the notifications request."""

    def __init__(self, session_response, notifications_response=None):
        """Store the responses."""
        self.session_response = session_response
        self.notifications_response = notifications_response
        self.posts = []
        self.gets = []

    def post(self, url, json=None, headers=None, **_kwargs):
        """Answer the login."""
        self.posts.append((url, json, headers))
        return self.session_response

    def get(self, url, params=None, headers=None, **_kwargs):
        """Answer the notifications request."""
        self.gets.append((url, params, headers))
        return self.notifications_response


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
    "type": "personal-news",
    "id": 1,
    "title": "Aangepaste ophaaldag",
    "description": "<p>Uw <b>GFT</b> wordt deze week op vrijdag opgehaald &amp; niet op donderdag.</p>",
    "date": "2026-11-10",
    "read": False,
    "newsId": 1,
}


def test_logs_in_with_the_address_and_returns_messages():
    """An address-only session yields the personal messages, cleaned up."""
    session = FakeSession(
        FakeResponse({"authToken": TOKEN, "authLevel": 1}), _page(PERSONAL)
    )

    result = rd4.get_notification_data_raw("rd4", "6417 at", "32", "", session=session)

    assert result == [
        {
            "id": 1,
            "type": "personal-news",
            "title": "Aangepaste ophaaldag",
            "content": "Uw GFT wordt deze week op vrijdag opgehaald & niet op donderdag.",
            "date": "2026-11-10",
            "dismissable": False,
        }
    ]
    url, body, headers = session.posts[0]
    assert url == "https://data.rd4.nl/api/v2/auth/session"
    assert body == {
        "type": "waste-card",
        "postalCode": "6417AT",
        "houseNr": 32,
        "houseNrExt": "",
        "wasteCardNr": None,
    }
    assert headers["X-Rd4-Client"] == "android/app.rd4.nl/4.6.2"
    assert "Authorization" not in headers
    url, params, headers = session.gets[0]
    assert url == "https://data.rd4.nl/api/v2/notifications"
    assert params["types[]"] == ["personal-news", "news"]
    assert headers["Authorization"] == f"Bearer {TOKEN}"


def test_suffix_is_sent_as_house_number_extension():
    """The suffix becomes houseNrExt."""
    session = FakeSession(FakeResponse({"authToken": TOKEN}), _page())

    rd4.get_notification_data_raw("rd4", "6417AT", "32", "a", session=session)

    assert session.posts[0][1]["houseNrExt"] == "A"


def test_wrapped_payloads_are_accepted():
    """A {"data": ...} wrapper around the session and page is unwrapped."""
    session = FakeSession(
        FakeResponse({"data": {"authToken": TOKEN}}),
        FakeResponse({"data": {"items": [PERSONAL]}}),
    )

    assert (
        len(rd4.get_notification_data_raw("rd4", "6417AT", "32", session=session)) == 1
    )


def test_other_types_and_empty_items_are_skipped():
    """Calendar reminders, tickets and empty messages are left out."""
    reminder = {**PERSONAL, "type": "waste-calendar", "pickUpDate": "2026-11-12"}
    empty = {**PERSONAL, "id": 8, "title": " ", "description": "<p></p>"}
    news = {
        **PERSONAL,
        "id": 9,
        "type": "news",
        "title": "Nieuws",
        "description": "Algemeen",
    }
    session = FakeSession(
        FakeResponse({"authToken": TOKEN}), _page(reminder, empty, news)
    )

    result = rd4.get_notification_data_raw("rd4", "6417AT", "32", session=session)

    assert [item["id"] for item in result] == [9]


def test_no_token_means_no_notifications():
    """Without a session token nothing else is requested."""
    session = FakeSession(FakeResponse({"authLevel": 0}))

    assert rd4.get_notification_data_raw("rd4", "6417AT", "32", session=session) == []
    assert session.gets == []


def test_request_errors_are_logged_without_details(caplog):
    """A failing request returns nothing and doesn't log the session token."""
    session = FakeSession(
        FakeResponse({"authToken": TOKEN}), FakeResponse({"code": 1}, status_code=401)
    )

    assert rd4.get_notification_data_raw("rd4", "6417AT", "32", session=session) == []
    assert "HTTPError" in caplog.text
    assert TOKEN not in caplog.text


def test_non_numeric_house_number_skips_notifications():
    """The app API wants a numeric house number."""
    session = FakeSession(FakeResponse({"authToken": TOKEN}))

    assert rd4.get_notification_data_raw("rd4", "6417AT", "32a", session=session) == []
    assert session.posts == []


def test_unknown_provider_is_rejected():
    """Only RD4 is accepted."""
    with pytest.raises(ValueError):
        rd4.get_notification_data_raw("rova", "6417AT", "32", session=FakeSession(None))


def test_rd4_advertises_notifications():
    """The notifications sensor is created for RD4."""
    assert MainCollector.provider_supports_notifications("rd4")
