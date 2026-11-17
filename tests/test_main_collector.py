"""Tests for MainCollector.provider_supports_notifications in main_collector.py."""

import contextlib
import json
import logging

import pytest
import requests

from custom_components.afvalwijzer.collector import main_collector
from custom_components.afvalwijzer.collector.main_collector import MainCollector
from custom_components.afvalwijzer.config_flow import ALL_COLLECTORS
from custom_components.afvalwijzer.const import const

from .fakes import FakeResponse


def test_opzet_provider_supports_notifications():
    """A provider from the opzet collector set supports notifications."""
    assert MainCollector.provider_supports_notifications("alphenaandenrijn") is True


def test_mijnafvalwijzer_provider_supports_notifications():
    """The mijnafvalwijzer provider supports notifications."""
    assert MainCollector.provider_supports_notifications("mijnafvalwijzer") is True


def test_unrelated_provider_does_not_support_notifications():
    """A provider outside the known notification-capable sets returns False."""
    assert MainCollector.provider_supports_notifications("rova") is False


def test_unknown_provider_does_not_support_notifications():
    """An unrecognized provider name returns False rather than raising."""
    assert MainCollector.provider_supports_notifications("not_a_real_provider") is False


def test_provider_supports_notifications_is_case_and_whitespace_insensitive():
    """Matching is normalized the same way MainCollector normalizes provider."""
    assert MainCollector.provider_supports_notifications(" MijnAfvalwijzer ") is True


def test_provider_supports_notifications_handles_none():
    """A missing provider (e.g. unset config) does not raise."""
    assert MainCollector.provider_supports_notifications(None) is False


# --- choosing the collector --------------------------------------------------------

# collector module name -> the constant listing its providers
PROVIDER_SETS = {
    "amsterdam": const.SENSOR_COLLECTORS_AMSTERDAM,
    "burgerportaal": const.SENSOR_COLLECTORS_BURGERPORTAAL,
    "circulus": const.SENSOR_COLLECTORS_CIRCULUS,
    "deafvalapp": const.SENSOR_COLLECTORS_DEAFVALAPP,
    "icalendar": const.SENSOR_COLLECTORS_ICALENDAR,
    "irado": const.SENSOR_COLLECTORS_IRADO,
    "klikogroep": const.SENSOR_COLLECTORS_KLIKOGROEP,
    "mijnafvalhulp": const.SENSOR_COLLECTORS_MIJNAFVALHULP,
    "mijnafvalwijzer": const.SENSOR_COLLECTORS_MIJNAFVALWIJZER,
    "montferland": const.SENSOR_COLLECTORS_MONTFERLAND,
    "omrin": const.SENSOR_COLLECTORS_OMRIN,
    "opzet": const.SENSOR_COLLECTORS_OPZET,
    "rd4": const.SENSOR_COLLECTORS_RD4,
    "recycleapp": const.SENSOR_COLLECTORS_RECYCLEAPP,
    "reinis": const.SENSOR_COLLECTORS_REINIS,
    "rova": const.SENSOR_COLLECTORS_ROVA,
    "straatbeeld": const.SENSOR_COLLECTORS_STRAATBEELD,
    "ximmio": const.SENSOR_COLLECTORS_XIMMIO_IDS,
}
ALL_PROVIDERS = [
    (module, provider) for module, names in PROVIDER_SETS.items() for provider in names
]
RAW = [{"type": "gft", "date": "2099-01-05"}]


def _build(provider="rova", **overrides):
    arguments = {
        "exclude_pickup_today": True,
        "exclude_list": "",
        "default_label": "geen",
        **overrides,
    }
    return MainCollector(provider, "1234 ab", " 5 ", "B", " Teststraat ", **arguments)


def _stub_all(monkeypatch, returns=None):
    """Replace every collector's getter with one that records its call."""
    calls = []
    for module in PROVIDER_SETS:

        def _getter(*args, _module=module, **kwargs):
            calls.append((_module, args, kwargs))
            return RAW if returns is None else returns

        monkeypatch.setattr(
            getattr(main_collector, module), "get_waste_data_raw", _getter
        )
    monkeypatch.setattr(main_collector, "NOTIFICATION_PROVIDERS", [])
    return calls


def test_no_provider_belongs_to_two_collectors():
    """A provider that two collectors list would silently use the first."""
    seen: dict[str, str] = {}
    for module, provider in ALL_PROVIDERS:
        assert provider not in seen, f"{provider}: {seen.get(provider)} and {module}"
        seen[provider] = module


@pytest.mark.parametrize(("module", "provider"), ALL_PROVIDERS)
def test_every_provider_reaches_its_own_collector(monkeypatch, module, provider):
    """The provider is handed to the collector that lists it, and to no other."""
    calls = _stub_all(monkeypatch)

    _build(provider)

    assert [call[0] for call in calls] == [module]
    _, args, kwargs = calls[0]
    assert args[:4] == (provider, "1234 AB", "5", "b")
    assert "session" in kwargs


def test_rwm_is_an_opzet_provider(monkeypatch):
    """RWM has no collector of its own: its provider goes to the Opzet collector."""
    calls = _stub_all(monkeypatch)

    _build("rwm")

    assert [call[0] for call in calls] == ["opzet"]
    assert not hasattr(main_collector, "rwm")
    assert "rwm" in ALL_COLLECTORS


def test_only_recycleapp_gets_the_street_name(monkeypatch):
    """The street name is an extra argument for the Belgian collector only."""
    calls = _stub_all(monkeypatch)

    _build("recycleapp")
    _build("rova")

    recycleapp_args, rova_args = calls[0][1], calls[1][1]
    assert recycleapp_args[4] == "teststraat"
    assert len(rova_args) == 4


def test_one_session_is_used_for_the_waste_and_the_notifications(monkeypatch):
    """Both requests share the connection of this refresh."""
    calls = _stub_all(monkeypatch)
    notification_sessions = []

    def _notifications(*_args, session=None, **_kwargs):
        notification_sessions.append(session)
        return []

    monkeypatch.setattr(
        main_collector, "NOTIFICATION_PROVIDERS", [(["rova"], _notifications)]
    )

    _build("rova")

    assert notification_sessions == [calls[0][2]["session"]]


def test_an_unknown_provider_is_logged_and_raised(monkeypatch, caplog):
    """A provider no collector knows is a configuration error."""
    _stub_all(monkeypatch)

    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(ValueError, match="Unknown provider"),
    ):
        _build("nonexistent")

    assert "Check afvalwijzer platform settings" in caplog.text


def test_a_collector_error_is_logged_and_raised(monkeypatch, caplog):
    """A collector that raises ValueError is reported, then raised as it is."""
    _stub_all(monkeypatch)

    def _failing(*_args, **_kwargs):
        raise ValueError("Rova request failed (HTTPError 503)")

    monkeypatch.setattr(main_collector.rova, "get_waste_data_raw", _failing)

    with (
        caplog.at_level(logging.ERROR),
        pytest.raises(ValueError, match="HTTPError 503"),
    ):
        _build("rova")

    assert "Check afvalwijzer platform settings: Rova request failed" in caplog.text


# --- the settings ------------------------------------------------------------------


def test_settings_are_normalized(monkeypatch):
    """Case and spacing of the settings don't matter."""
    _stub_all(monkeypatch)

    collector = main_collector.MainCollector(
        " ROVA ",
        " 1234 ab ",
        " 5 ",
        " B ",
        " Teststraat ",
        exclude_pickup_today=" TRUE ",
        exclude_list=" GFT, Papier ",
        default_label=" geen ",
    )

    assert collector.provider == "rova"
    assert collector.postal_code == "1234 AB"
    assert collector.house_number == "5"
    assert collector.suffix == "b"
    assert collector.street_name == "teststraat"
    assert collector.exclude_pickup_today == "true"
    assert collector.exclude_list == "gft, papier"
    assert collector.default_label == "geen"


@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, "true"), (False, "false"), ("False", "false"), (" No ", "no")],
)
def test_exclude_pickup_today_accepts_booleans_and_text(monkeypatch, value, expected):
    """A boolean from the options and text from yaml both end up as lower case text."""
    _stub_all(monkeypatch)

    assert _build(exclude_pickup_today=value).exclude_pickup_today == expected


def test_the_properties_come_from_the_transformed_data(monkeypatch):
    """The collector exposes what the transformer built."""
    _stub_all(monkeypatch, returns=[{"type": "gft", "date": "2099-01-05"}])

    collector = _build("rova")

    assert collector.waste_types_provider == ["gft"]
    assert collector.waste_data_raw[0]["type"] == "gft"
    assert set(collector.waste_data_with_today) == {"gft"}
    assert set(collector.waste_data_without_today) == {"gft"}
    assert set(collector.waste_data_provider) == {"gft"}
    assert "next_type" in collector.waste_data_custom
    assert "next_type" in collector.waste_types_custom


# --- notifications -----------------------------------------------------------------


def test_notifications_are_fetched_for_a_provider_that_has_them(monkeypatch):
    """The getter of the matching provider set is called with the address."""
    _stub_all(monkeypatch)
    received = []
    notices = [{"title": "Storing"}, {"title": "Feestdagen"}]

    def _notifications(*args, session=None, **_kwargs):
        received.append(args)
        return notices

    monkeypatch.setattr(
        main_collector, "NOTIFICATION_PROVIDERS", [({"rova": 1}, _notifications)]
    )

    collector = _build("rova")

    assert collector.notification_data == notices
    assert collector.notification_count == 2
    assert received == [("rova", "1234 AB", "5", "b")]


def test_a_provider_without_notifications_has_none(monkeypatch):
    """No getter means an empty list, and a debug line."""
    _stub_all(monkeypatch)

    collector = _build("rova")

    assert collector.notification_data == []
    assert collector.notification_count == 0


def test_a_failing_notification_fetch_is_only_a_warning(monkeypatch, caplog):
    """The waste data is still shown when the notifications can't be fetched."""
    _stub_all(monkeypatch)

    def _failing(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(
        main_collector, "NOTIFICATION_PROVIDERS", [(["rova"], _failing)]
    )

    with caplog.at_level(logging.WARNING):
        collector = _build("rova")

    assert collector.notification_data == []
    assert collector.waste_types_provider == ["gft"]
    assert "Could not fetch notification data for rova: boom" in caplog.text


# --- answers of the wrong shape ----------------------------------------------------


@pytest.mark.parametrize("error", [AttributeError("x"), KeyError("x"), TypeError("x")])
def test_a_collector_that_chokes_on_its_data_is_reported_as_invalid_data(
    monkeypatch, error, caplog
):
    """Whatever the collector trips over, the user sees one clear message."""
    _stub_all(monkeypatch)

    def _failing(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(main_collector.rova, "get_waste_data_raw", _failing)

    with caplog.at_level(logging.ERROR), pytest.raises(ValueError) as raised:
        _build("rova")

    assert str(raised.value) == "Invalid and/or no data received from rova"
    assert raised.value.__cause__ is error
    assert "Invalid and/or no data received from rova" in caplog.text


# JSON a provider could answer with, whatever the collector expects
MALFORMED_ANSWERS = [
    [],
    "text",
    5,
    None,
    {"a": []},
    {"data": 5},
    {"customData": []},
    [[]],
    [5],
    {"items": 5},
    {"dataList": 5},
    {"calendar": []},
]


class _AnsweringSession:
    """Session answering every request with the same payload."""

    def __init__(self, payload):
        self.response = FakeResponse(
            payload,
            text=json.dumps(payload) if payload is not None else "",
            url="https://x/",
            cookies={"CB_SESSION": "x__AT=t&___TS=1"},
        )
        self.cookies = requests.cookies.RequestsCookieJar()
        self.headers = {}

    def _answer(self, *_args, **_kwargs):
        return self.response

    get = post = put = request = _answer


@pytest.mark.parametrize("payload", MALFORMED_ANSWERS, ids=repr)
@pytest.mark.parametrize("module", sorted(PROVIDER_SETS))
def test_every_collector_survives_an_answer_of_the_wrong_shape(
    monkeypatch, module, payload
):
    """No collector lets an AttributeError, KeyError or TypeError through."""
    provider = next(name for name in PROVIDER_SETS[module])
    monkeypatch.setattr(
        main_collector.requests, "Session", lambda: _AnsweringSession(payload)
    )
    monkeypatch.setattr(main_collector, "NOTIFICATION_PROVIDERS", [])

    # a ValueError is fine (the user sees a clear message); anything else fails
    with contextlib.suppress(ValueError):
        _build(provider)
