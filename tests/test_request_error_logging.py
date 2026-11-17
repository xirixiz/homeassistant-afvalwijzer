"""Request errors must not put the address in the log or in the raised error.

The message of a requests exception includes the request URL, and for most
collectors the URL holds the postal code and house number. The log ends up in the
logs people paste into issues, so every collector describes a request error by its
type and HTTP status only.
"""

import importlib
import logging

import pytest
import requests

from custom_components.afvalwijzer.collector import amsterdam, icalendar
from custom_components.afvalwijzer.common.main_functions import (
    describe_request_error,
)

POSTAL_CODE = "9876ZX"
HOUSE_NUMBER = "4321"
URL = f"https://example.nl/api?postcode={POSTAL_CODE}&huisnummer={HOUSE_NUMBER}"

# (module, provider, extra keyword arguments). The first request of each fails.
COLLECTORS = [
    ("amsterdam", "amsterdam", {}),
    ("burgerportaal", "assen", {}),
    ("circulus", "circulus", {}),
    ("deafvalapp", "deafvalapp", {}),
    ("icalendar", "borsele", {}),
    ("irado", "irado", {}),
    ("klikogroep", "oudeijsselstreek", {}),
    ("mijnafvalhulp", "mijnafvalhulp", {}),
    ("mijnafvalwijzer", "mijnafvalwijzer", {}),
    ("montferland", "montferland", {}),
    ("omrin", "omrin", {}),
    ("opzet", "alphenaandenrijn", {}),
    ("rd4", "rd4", {}),
    ("recycleapp", "recycleapp", {"street_name": "Teststraat"}),
    ("reinis", "reinis", {}),
    ("rova", "rova", {}),
    ("rwm", "rwm", {}),
    ("straatbeeld", "straatbeeld", {}),
    ("ximmio", "avalex", {}),
]


class _Response:
    status_code = 503


def _connection_error():
    return requests.exceptions.ConnectionError(
        "HTTPSConnectionPool(host='example.nl', port=443): Max retries exceeded "
        f"with url: /api?postcode={POSTAL_CODE}&huisnummer={HOUSE_NUMBER} "
        "(Caused by NameResolutionError())"
    )


def _http_error():
    return requests.exceptions.HTTPError(
        f"503 Server Error: Service Unavailable for url: {URL}", response=_Response()
    )


class _FailingSession:
    """Session whose requests all fail with the same kind of error."""

    def __init__(self, make_error):
        """Store how to make the error."""
        self.make_error = make_error
        self.cookies = requests.cookies.RequestsCookieJar()
        self.headers = {}

    def _fail(self, *_args, **_kwargs):
        raise self.make_error()

    get = post = put = request = _fail


@pytest.mark.parametrize("make_error", [_connection_error, _http_error])
@pytest.mark.parametrize(("module", "provider", "extra"), COLLECTORS)
def test_request_errors_do_not_expose_the_address(
    module, provider, extra, make_error, caplog
):
    """Neither the log nor the exception holds the postal code, house number or URL."""
    collector = importlib.import_module(
        f"custom_components.afvalwijzer.collector.{module}"
    )

    with caplog.at_level(logging.DEBUG), pytest.raises(ValueError) as raised:
        collector.get_waste_data_raw(
            provider,
            POSTAL_CODE,
            HOUSE_NUMBER,
            "",
            session=_FailingSession(make_error),
            **extra,
        )

    logged = caplog.text
    chain = []
    error = raised.value
    while error is not None:
        chain.append(str(error))
        error = error.__cause__
    # the error that was raised is what Home Assistant logs; the cause is not
    message = chain[0]
    for text in (logged, message):
        assert POSTAL_CODE not in text
        assert HOUSE_NUMBER not in text
        assert "example.nl" not in text
        assert "huisnummer" not in text


@pytest.mark.parametrize(
    ("make_error", "expected"),
    [(_connection_error, "ConnectionError"), (_http_error, "HTTPError 503")],
)
def test_describe_request_error(make_error, expected):
    """The type, and the HTTP status when there is one."""
    assert describe_request_error(make_error()) == expected


def test_describe_request_error_without_a_response():
    """An HTTPError built without a response has no status."""
    assert describe_request_error(requests.exceptions.HTTPError("x")) == "HTTPError"


def test_describe_request_error_for_any_exception():
    """The helper doesn't depend on the error being a requests error."""
    assert describe_request_error(TimeoutError("slow")) == "TimeoutError"


# --- "invalid data" errors: no request URL either -----------------------------------


class _Answer:
    """A successful response with a body the collector can't make sense of."""

    status_code = 200
    url = URL
    headers = {"Content-Type": "application/json"}

    def __init__(self, payload=None, text=""):
        """Store the JSON payload and the text."""
        self._payload = payload
        self.text = text
        self.content = b"x"

    def json(self):
        """Return the payload."""
        return self._payload

    def raise_for_status(self):
        """Never fail."""


class _AnsweringSession:
    """Session answering every request with the same response."""

    def __init__(self, answer):
        """Store the answer."""
        self.answer = answer

    def _answer(self, *_args, **_kwargs):
        return self.answer

    get = post = _answer


_BAD_DATE = "not-a-date"

# collector, provider, a response its parser can't handle, expected exception type
INVALID_DATA = [
    ("mijnafvalwijzer", "mijnafvalwijzer", _Answer({}), KeyError),
    (
        "rova",
        "rova",
        _Answer([{"date": _BAD_DATE, "wasteType": {"title": "GFT"}}]),
        ValueError,
    ),
    (
        "klikogroep",
        "oudeijsselstreek",
        _Answer({"calendar": {_BAD_DATE: ["GFT"]}}),
        ValueError,
    ),
    (
        "irado",
        "irado",
        _Answer(
            {
                "valid": True,
                "calendar_data": {
                    "pickups": {
                        "2026": {"11": {"1": [{"date": _BAD_DATE, "type": "gft"}]}}
                    }
                },
            }
        ),
        ValueError,
    ),
    (
        "rd4",
        "rd4",
        _Answer(
            {"success": True, "data": {"items": [[{"date": _BAD_DATE, "type": "gft"}]]}}
        ),
        ValueError,
    ),
    ("deafvalapp", "deafvalapp", _Answer(text=f"GFT;{_BAD_DATE};\n"), ValueError),
]


@pytest.mark.parametrize(("module", "provider", "answer", "error_type"), INVALID_DATA)
def test_invalid_data_errors_do_not_expose_the_address(
    module, provider, answer, error_type, caplog
):
    """The error says which collector had a problem, not which URL was asked."""
    collector = importlib.import_module(
        f"custom_components.afvalwijzer.collector.{module}"
    )

    with caplog.at_level(logging.DEBUG), pytest.raises(error_type) as raised:
        collector.get_waste_data_raw(
            provider,
            POSTAL_CODE,
            HOUSE_NUMBER,
            "",
            session=_AnsweringSession(answer),
        )

    assert "Invalid and/or no data received from" in str(raised.value)
    for text in (caplog.text, str(raised.value)):
        assert POSTAL_CODE not in text
        assert HOUSE_NUMBER not in text
        assert "example.nl" not in text


def test_icalendar_invalid_data_error_does_not_expose_the_address(caplog, monkeypatch):
    """A feed that can't be parsed is reported without the feed URL."""

    def _broken(*_args, **_kwargs):
        raise ValueError("cannot parse")

    monkeypatch.setattr(icalendar, "parse_ical_waste_data", _broken)
    session = _AnsweringSession(_Answer(text="BEGIN:VCALENDAR\r\nEND:VCALENDAR"))

    with caplog.at_level(logging.DEBUG), pytest.raises(ValueError) as raised:
        icalendar.get_waste_data_raw(
            "borsele", POSTAL_CODE, HOUSE_NUMBER, "", session=session
        )

    assert "Invalid and/or no data received from iCalendar" in str(raised.value)
    for text in (caplog.text, str(raised.value)):
        assert POSTAL_CODE not in text
        assert HOUSE_NUMBER not in text


def test_amsterdam_without_a_valid_answer_does_not_expose_the_address():
    """Every suffix variant answered with an empty body: the error has no URL."""
    session = _AnsweringSession(_Answer({}, text="{}"))

    with pytest.raises(ValueError) as raised:
        amsterdam._fetch_waste_data_raw_temp(
            session,
            "https://example.nl",
            [{"postcode": POSTAL_CODE, "huisnummer": HOUSE_NUMBER}],
            timeout=(1, 1),
            verify=True,
        )

    assert "Invalid and/or no data received from AMSTERDAM" in str(raised.value)
    assert POSTAL_CODE not in str(raised.value)


@pytest.mark.parametrize(
    ("module", "notify", "label"),
    [
        ("mijnafvalwijzer", "MijnAfvalWijzer", "mijnafvalwijzer"),
        ("opzet", "OPZET", "alphenaandenrijn"),
    ],
)
def test_notification_request_errors_do_not_expose_the_address(
    module, notify, label, caplog
):
    """The notification fetch only warns, but the warning must not hold the URL."""
    collector = importlib.import_module(
        f"custom_components.afvalwijzer.collector.{module}"
    )

    with caplog.at_level(logging.DEBUG):
        result = collector.get_notification_data_raw(
            label, POSTAL_CODE, HOUSE_NUMBER, "", session=_FailingSession(_http_error)
        )

    assert result == []
    assert f"{notify} notification request error (HTTPError 503)" in caplog.text
    assert POSTAL_CODE not in caplog.text
    assert HOUSE_NUMBER not in caplog.text


@pytest.mark.parametrize(
    ("module", "provider"), [("rova", "rova"), ("klikogroep", "oudeijsselstreek")]
)
def test_a_body_that_is_not_json_is_a_request_error(module, provider, caplog):
    """Requests' JSONDecodeError is a RequestException, so it takes that path."""
    collector = importlib.import_module(
        f"custom_components.afvalwijzer.collector.{module}"
    )

    def _not_json():
        raise requests.exceptions.JSONDecodeError("Expecting value", "<html>", 0)

    answer = _Answer()
    answer.json = _not_json

    with caplog.at_level(logging.DEBUG), pytest.raises(ValueError) as raised:
        collector.get_waste_data_raw(
            provider, POSTAL_CODE, HOUSE_NUMBER, "", session=_AnsweringSession(answer)
        )

    assert "request failed (JSONDecodeError)" in str(raised.value)
    assert POSTAL_CODE not in caplog.text
