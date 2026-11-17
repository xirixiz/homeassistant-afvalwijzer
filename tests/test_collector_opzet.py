"""Tests for the Opzet collector: address lookup, notifications and error handling."""

import pytest
import requests

from custom_components.afvalwijzer.collector import opzet

BASE = opzet._build_base_url("hvc")


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


class FakeSession:
    """Session answering by URL, remembering every request."""

    def __init__(self, *, addresses=None, streams=None, notices=None, error=None):
        """Store the payloads; error makes every request fail with that exception."""
        self.addresses = [{"bagId": "bag1"}] if addresses is None else addresses
        self.streams = [] if streams is None else streams
        self.notices = [] if notices is None else notices
        self.error = error
        self.urls = []

    def get(self, url, **_kwargs):
        """Answer an address, stream, calendar or notification request."""
        self.urls.append(url.removeprefix(BASE))
        if self.error is not None:
            raise self.error
        if "/rest/adressen/" in url and url.endswith("/afvalstromen"):
            return _answer(self.streams)
        if "/kalender/" in url:
            return FakeResponse({}, status_code=404)
        if "/rest/app/meldingen/" in url:
            return _answer(self.notices)
        return _answer(self.addresses)

    def count(self, fragment):
        """Return how many requests contained the fragment."""
        return sum(fragment in url for url in self.urls)


def _answer(payload):
    return payload if isinstance(payload, FakeResponse) else FakeResponse(payload)


@pytest.fixture(autouse=True)
def _clear_bag_cache():
    opzet._BAG_ID_CACHE.clear()
    yield
    opzet._BAG_ID_CACHE.clear()


# --- provider and bag id ------------------------------------------------------------


def test_build_base_url_rejects_an_unknown_provider():
    """Only the Opzet providers are accepted."""
    with pytest.raises(ValueError, match="Invalid provider"):
        opzet._build_base_url("amsterdam")


def test_bag_id_is_looked_up_once_per_address():
    """A second refresh reuses the bag id instead of asking again."""
    session = FakeSession()
    args = (session, BASE, "1234AB", "1", "")

    assert opzet._get_bag_id(*args, timeout=(1, 1), verify=True) == "bag1"
    assert opzet._get_bag_id(*args, timeout=(1, 1), verify=True) == "bag1"

    assert session.count("/rest/adressen/1234AB-1") == 1


def test_bag_id_cache_is_per_suffix():
    """5 and 5A are different addresses."""
    session = FakeSession(
        addresses=[
            {"bagId": "bag-a", "huisletter": "A"},
            {"bagId": "bag-b", "huisletter": "B"},
        ]
    )

    first = opzet._get_bag_id(
        session, BASE, "1234AB", "5", "A", timeout=(1, 1), verify=True
    )
    second = opzet._get_bag_id(
        session, BASE, "1234AB", "5", "B", timeout=(1, 1), verify=True
    )

    assert (first, second) == ("bag-a", "bag-b")
    assert session.count("/rest/adressen/1234AB-5") == 2


@pytest.mark.parametrize("addresses", [[], [{"huisletter": "A"}]])
def test_unknown_address_is_not_cached(addresses):
    """Nothing is remembered when no bag id was found (no addresses, or no bagId)."""
    session = FakeSession(addresses=addresses)

    result = opzet._get_bag_id(
        session, BASE, "1234AB", "1", "", timeout=(1, 1), verify=True
    )

    assert result is None
    assert opzet._BAG_ID_CACHE == {}


# --- waste data ---------------------------------------------------------------------


STREAMS = [
    {"id": 1, "menu_title": "GFT", "ophaaldatum": "2026-11-20"},
    {"id": 2, "menu_title": "Restafval", "ophaaldatum": "2026-11-27"},
]


def test_parse_waste_data_raw_maps_types_and_skips_incomplete_items():
    """Streams without a date or a title are skipped, the rest is mapped."""
    items = [
        {"menu_title": "GFT", "ophaaldatum": "2026-11-20"},
        {"menu_title": "Restafval", "ophaaldatum": ""},
        {"menu_title": "Papier"},
        {"menu_title": "", "ophaaldatum": "2026-11-21"},
        {"ophaaldatum": "2026-11-22"},
        {"menu_title": "Wintertuin", "ophaaldatum": "2026-12-01"},
    ]

    assert opzet._parse_waste_data_raw(items) == [
        {"type": "gft", "date": "2026-11-20"},
        {"type": "wintertuin", "date": "2026-12-01"},
    ]


@pytest.mark.freeze_time("2026-11-17 09:00:00")
def test_get_waste_data_raw_returns_the_next_pickups():
    """Without a calendar every stream still gives its next pickup."""
    session = FakeSession(streams=STREAMS)

    result = opzet.get_waste_data_raw("hvc", "1234AB", "1", "", session=session)

    assert result == [
        {"type": "gft", "date": "2026-11-20"},
        {"type": "restafval", "date": "2026-11-27"},
    ]


@pytest.mark.freeze_time("2026-11-17 09:00:00")
def test_get_waste_data_raw_without_a_bag_id_returns_nothing(caplog):
    """An address Opzet doesn't know is an empty schedule, with a warning."""
    session = FakeSession(addresses=[])

    assert opzet.get_waste_data_raw("hvc", "1234AB", "1", "", session=session) == []
    assert "Address/bag_id not found" in caplog.text
    assert session.count("/afvalstromen") == 0


@pytest.mark.freeze_time("2026-11-17 09:00:00")
def test_get_waste_data_raw_wraps_request_errors():
    """Network errors are raised as ValueError for the coordinator."""
    session = FakeSession(error=requests.exceptions.ConnectionError("down"))

    with pytest.raises(ValueError):
        opzet.get_waste_data_raw("hvc", "1234AB", "1", "", session=session)


@pytest.mark.freeze_time("2026-11-17 09:00:00")
def test_get_waste_data_raw_wraps_invalid_data():
    """Streams of the wrong shape are raised as ValueError."""
    session = FakeSession(streams=[{"menu_title": "GFT", "ophaaldatum": "morgen"}])

    with pytest.raises(ValueError, match="Invalid and/or no data"):
        opzet.get_waste_data_raw("hvc", "1234AB", "1", "", session=session)


def test_get_waste_data_raw_rejects_an_unknown_provider():
    """Only the Opzet providers are accepted."""
    with pytest.raises(ValueError, match="Invalid provider"):
        opzet.get_waste_data_raw("amsterdam", "1234AB", "1", "", session=FakeSession())


# --- notifications ------------------------------------------------------------------


def test_notification_is_cleaned():
    """HTML is stripped, entities decoded and the text trimmed."""
    notices = [
        {
            "id": 12,
            "kop": "Storing",
            "content": "<p> Zet het afval <b>vrijdag</b> buiten &amp; wacht. </p>",
            "afwijsbaar": 1,
        }
    ]

    assert opzet._parse_notification_data_raw(notices) == [
        {
            "id": 12,
            "title": "Storing",
            "content": "Zet het afval vrijdag buiten & wacht.",
            "dismissable": True,
        }
    ]


@pytest.mark.parametrize(
    ("flag", "dismissable"), [(1, True), (True, True), (0, False), (None, False)]
)
def test_notification_dismissable_flag(flag, dismissable):
    """The provider's afwijsbaar flag decides whether it can be dismissed."""
    [result] = opzet._parse_notification_data_raw(
        [{"id": 1, "kop": "x", "content": "Tekst", "afwijsbaar": flag}]
    )

    assert result["dismissable"] is dismissable


def test_notification_without_a_dismissable_flag_or_title_uses_defaults():
    """Only the content is required."""
    [result] = opzet._parse_notification_data_raw([{"content": "Tekst"}])

    assert result == {"id": None, "title": "", "content": "Tekst", "dismissable": False}


@pytest.mark.parametrize("content", [None, "", "<p></p>", "<br/>  &nbsp;"])
def test_notification_without_text_is_skipped(content):
    """A notice that says nothing is not shown."""
    assert opzet._parse_notification_data_raw([{"id": 1, "content": content}]) == []


def test_get_notification_data_raw_fetches_for_the_address():
    """The notices are read for the address's bag id."""
    notices = [{"id": 1, "kop": "Storing", "content": "Tekst", "afwijsbaar": 0}]
    session = FakeSession(notices=notices)

    result = opzet.get_notification_data_raw("hvc", "1234AB", "1", "", session=session)

    assert [n["id"] for n in result] == [1]
    assert "/rest/app/meldingen/bag1" in session.urls


def test_get_notification_data_raw_without_a_bag_id_returns_nothing():
    """An unknown address has no notices, and nothing more is requested."""
    session = FakeSession(addresses=[])

    assert (
        opzet.get_notification_data_raw("hvc", "1234AB", "1", "", session=session) == []
    )
    assert session.count("/meldingen/") == 0


def test_get_notification_data_raw_ignores_request_errors(caplog):
    """Notices are optional: a failing request gives none, and a warning."""
    session = FakeSession(error=requests.exceptions.ConnectionError("down"))

    assert (
        opzet.get_notification_data_raw("hvc", "1234AB", "1", "", session=session) == []
    )
    assert "notification request error" in caplog.text


def test_get_notification_data_raw_ignores_invalid_data(caplog):
    """An answer of the wrong shape gives no notices, and a warning."""
    session = FakeSession(notices=[{"content": 5}])

    assert (
        opzet.get_notification_data_raw("hvc", "1234AB", "1", "", session=session) == []
    )
    assert "Invalid notification data" in caplog.text


def test_get_notification_data_raw_rejects_an_unknown_provider():
    """Only the Opzet providers are accepted."""
    with pytest.raises(ValueError, match="Invalid provider"):
        opzet.get_notification_data_raw(
            "amsterdam", "1234AB", "1", "", session=FakeSession()
        )


def test_no_addresses_selects_no_bag_id():
    """An empty address list has no bag id to select."""
    assert opzet._select_bag_id([], "") is None
    assert opzet._select_bag_id([], "A") is None
