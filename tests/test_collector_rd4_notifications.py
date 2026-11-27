"""Tests for the RD4 app notifications (address-only session)."""

from datetime import UTC, datetime, timedelta

import pytest
import requests

from custom_components.afvalwijzer.collector import rd4
from custom_components.afvalwijzer.collector.main_collector import MainCollector

API = "https://data.rd4.nl/api/v2"
TOKEN = "session-token"
RD4_CLIENT, GEUL_EN_MAAS_CLIENT = rd4._APP_CLIENTS
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

    def __init__(
        self,
        notifications=None,
        *,
        token=TOKEN,
        session_status=201,
        served_clients=None,
        articles=None,
    ):
        """Store the answers; notifications may be a list of answers in order.

        served_clients limits the clients that get a session, like the real API
        does per region. The others are answered with 403. None serves all.
        articles maps a newsId to the article behind a message; others are 404.
        """
        self.articles = articles or {}
        self.article_calls = []
        self.token = token
        self.session_status = session_status
        self.served_clients = served_clients
        self.notifications = (
            notifications if notifications is not None else [_page(PERSONAL)]
        )
        self.calls = []

    def post(self, url, json=None, headers=None, **_kwargs):
        """Answer the login."""
        self.calls.append(("POST", url, json, headers))
        if self.served_clients is not None and (
            headers["X-Rd4-Client"] not in self.served_clients
        ):
            message = "Client isn't allowed to make this request"
            return FakeResponse({"code": 4, "message": message}, 403)
        payload = {"authToken": self.token, "authLevel": 1} if self.token else {}
        return FakeResponse(payload, self.session_status)

    def put(self, url, headers=None, **_kwargs):
        """Answer the terms agreement."""
        self.calls.append(("PUT", url, None, headers))
        return FakeResponse(status_code=204)

    def get(self, url, params=None, headers=None, **_kwargs):
        """Answer the current terms or the notifications."""
        if url.startswith(f"{API}/news/"):
            # Kept apart from calls: every message has an article to look up.
            news_id = url.removeprefix(f"{API}/news/")
            self.article_calls.append(news_id)
            if news_id in self.articles:
                return FakeResponse(self.articles[news_id])
            return FakeResponse({"code": 5}, 404)
        self.calls.append(("GET", url, params, headers))
        if url == f"{API}/tos/current":
            return FakeResponse({"id": 1, "contents": "<p>Algemene voorwaarden</p>"})
        if url == f"{API}/notifications":
            if isinstance(self.notifications, list):
                return self.notifications.pop(0)
            return self.notifications
        raise AssertionError(f"unexpected URL {url}")

    def clients(self):
        """Return the X-Rd4-Client header of every request, in order."""
        return [headers["X-Rd4-Client"] for _, _, _, headers in self.calls]

    def urls(self):
        """Return the requests as 'METHOD path'."""
        return [f"{method} {url.removeprefix(API)}" for method, url, _, _ in self.calls]


@pytest.fixture(autouse=True)
def _clear_cache():
    rd4._SESSION_CACHE.clear()
    yield
    rd4._SESSION_CACHE.clear()


def _run(session, house_number="32", suffix="", postal_code="6417 at"):
    return rd4.get_notification_data_raw(
        "rd4", postal_code, house_number, suffix, session=session
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
    assert rd4._SESSION_CACHE
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
    assert rd4._SESSION_CACHE == {}


@pytest.mark.parametrize("status", [401, 403])
def test_address_not_served_by_the_app_api_is_not_a_warning(status, caplog):
    """403 (another client's region) or 401 (unknown address) at login is quiet."""
    session = FakeSession(session_status=status)

    with caplog.at_level("DEBUG"):
        assert _run(session) == []

    assert not [r for r in caplog.records if r.levelname == "WARNING"]
    assert "no app serves this address" in caplog.text
    assert session.urls() == ["POST /auth/session", "POST /auth/session"]
    assert session.clients() == [RD4_CLIENT, GEUL_EN_MAAS_CLIENT]
    assert rd4._SESSION_CACHE == {}


def test_other_login_errors_are_still_warnings(caplog):
    """A server error at login is reported."""
    session = FakeSession(session_status=503)

    assert _run(session) == []

    assert "could not fetch notifications (HTTPError)" in caplog.text
    assert session.urls() == ["POST /auth/session"]  # no fallback on a server error


def test_rd4_address_uses_only_the_rd4_client():
    """The first client serves RD4's own municipalities, so no second attempt."""
    session = FakeSession(served_clients={RD4_CLIENT})

    assert len(_run(session)) == 1
    assert set(session.clients()) == {RD4_CLIENT}


def test_geul_en_maas_address_falls_back_to_the_geul_en_maas_client():
    """Maastricht, Meerssen and Valkenburg are refused by the RD4 client."""
    session = FakeSession(served_clients={GEUL_EN_MAAS_CLIENT})

    result = _run(session, "11", postal_code="6225 ch")

    assert len(result) == 1
    assert session.urls() == [
        "POST /auth/session",  # refused (403) for the RD4 client
        "POST /auth/session",
        "GET /tos/current",
        "PUT /tos/1/agree",
        "GET /notifications",
    ]
    assert session.clients() == [RD4_CLIENT] + [GEUL_EN_MAAS_CLIENT] * 4
    assert rd4._SESSION_CACHE[("6225CH", 11, "")][0] == GEUL_EN_MAAS_CLIENT


def test_cached_geul_en_maas_session_keeps_using_its_client():
    """A refresh is one request, with the client that worked."""
    _run(FakeSession(served_clients={GEUL_EN_MAAS_CLIENT}), "11", postal_code="6225CH")
    session = FakeSession(served_clients={GEUL_EN_MAAS_CLIENT})

    assert len(_run(session, "11", postal_code="6225CH")) == 1
    assert session.urls() == ["GET /notifications"]
    assert session.clients() == [GEUL_EN_MAAS_CLIENT]


def test_rejected_geul_en_maas_session_tries_its_own_client_first():
    """After a rejected token the client that worked before is tried first."""
    _run(FakeSession(served_clients={GEUL_EN_MAAS_CLIENT}), "11", postal_code="6225CH")
    rejected = FakeResponse({"code": 3}, status_code=403)
    session = FakeSession(
        [rejected, _page(PERSONAL)], served_clients={GEUL_EN_MAAS_CLIENT}
    )

    assert len(_run(session, "11", postal_code="6225CH")) == 1
    assert session.urls() == [
        "GET /notifications",
        "POST /auth/session",
        "GET /tos/current",
        "PUT /tos/1/agree",
        "GET /notifications",
    ]
    assert set(session.clients()) == {GEUL_EN_MAAS_CLIENT}  # no RD4 attempt


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


def test_message_keeps_links_as_markdown():
    """A link in the description stays clickable (Markdown) and is listed in links."""
    item = {
        **PERSONAL,
        "description": '<p>Zie <a href="https://www.rd4.nl/nieuws">het nieuws</a>.</p>',
    }

    [result] = rd4._parse_notifications([item])

    assert result["content"] == "Zie [het nieuws](https://www.rd4.nl/nieuws)."
    assert result["links"] == [
        {"text": "het nieuws", "url": "https://www.rd4.nl/nieuws"}
    ]


ARTICLE = {
    "id": "1",
    "contents": (
        "<p>Meer info in de "
        '<a href="https://rd4.nl/afvalstoffenheffing">tarieven</a>.</p>'
    ),
    "cta": {
        "title": "Lees meer over minder GFT-afval",
        "link": "https://rd4.nl/mindergft",
    },
}


def test_article_links_are_added_to_the_message():
    """The call to action and the links in the article show up with the message."""
    session = FakeSession(articles={"1": ARTICLE})

    [result] = _run(session)

    assert session.article_calls == ["1"]
    assert result["links"] == [
        {"text": "Lees meer over minder GFT-afval", "url": "https://rd4.nl/mindergft"},
        {"text": "tarieven", "url": "https://rd4.nl/afvalstoffenheffing"},
    ]
    assert result["content"].endswith(
        "\n\n[Lees meer over minder GFT-afval](https://rd4.nl/mindergft)"
        "\n\n[tarieven](https://rd4.nl/afvalstoffenheffing)"
    )


def test_article_without_links_leaves_the_message_alone():
    """An article without a call to action or links changes nothing."""
    session = FakeSession(
        articles={"1": {"contents": "<p>Geen links</p>", "cta": None}}
    )

    [result] = _run(session)

    assert "links" not in result
    assert result["content"].startswith("Jouw GFT-container")


def test_unavailable_article_keeps_the_message():
    """A 404 (or any request error) on the article doesn't cost the message."""
    session = FakeSession()  # every article answers 404

    [result] = _run(session)

    assert session.article_calls == ["1"]
    assert result["title"] == "Aangepaste ophaaldag"
    assert "links" not in result


def test_unsafe_call_to_action_is_ignored():
    """A call to action that is not http(s) is not used."""
    session = FakeSession(
        articles={"1": {"cta": {"title": "x", "link": "javascript:alert(1)"}}}
    )

    [result] = _run(session)

    assert "links" not in result
