"""Tests for the Irado collector."""

import pytest
import requests

from custom_components.afvalwijzer.collector import irado

PICKUPS = {
    "valid": True,
    "calendar_data": {
        "pickups": {"2026": {"12": {"9": [{"date": "09/12/2026", "type": "gft"}]}}}
    },
}


class FakeResponse:
    """Minimal requests.Response stand-in."""

    def __init__(self, text="", *, payload=None, status_code=200, content_type=None):
        """Store the body, an optional JSON payload and the headers."""
        self.text = text
        self.content = text.encode()
        self._payload = payload
        self.status_code = status_code
        self.headers = {"Content-Type": content_type} if content_type else {}

    def json(self):
        """Return the payload, or fail like requests does for a non-JSON body."""
        if self._payload is None:
            raise requests.exceptions.JSONDecodeError("Expecting value", self.text, 0)
        return self._payload

    def raise_for_status(self):
        """Raise HTTPError for error statuses."""
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)


class FakeSession:
    """Session returning one response and remembering the request."""

    def __init__(self, response):
        """Store the response."""
        self.response = response
        self.urls = []

    def get(self, url, **_kwargs):
        """Return the response."""
        self.urls.append(url)
        return self.response


def test_irado_returns_the_pickups():
    """A normal response is parsed."""
    session = FakeSession(FakeResponse("{}", payload=PICKUPS))

    result = irado.get_waste_data_raw("irado", "2903 LS", "16", "", session=session)

    assert result == [{"type": "gft", "date": "2026-12-09"}]
    assert "zipcode=2903LS" in session.urls[0]


@pytest.mark.parametrize(
    ("body", "content_type"),
    [
        ("", "text/html; charset=UTF-8"),
        ("<html><body>Access   denied\n for this IP</body></html>", "text/html"),
        ("", None),
    ],
)
def test_irado_logs_what_it_received_when_it_is_not_json(body, content_type, caplog):
    """A body that isn't JSON is reported with status, type and a snippet."""
    session = FakeSession(FakeResponse(body, content_type=content_type))

    with pytest.raises(ValueError):
        irado.get_waste_data_raw("irado", "2903LS", "16", "", session=session)

    assert "Irado: response is not JSON (HTTP 200," in caplog.text
    assert f"{len(body.encode())} bytes" in caplog.text
    assert (content_type or "no content type") in caplog.text
    if body:
        assert "Access denied for this IP" in caplog.text


def test_irado_does_not_log_the_address_or_url(caplog):
    """The URL holds the postal code and house number, so it stays out of the log."""
    session = FakeSession(
        FakeResponse("<html>blocked</html>", content_type="text/html")
    )

    with pytest.raises(ValueError):
        irado.get_waste_data_raw("irado", "2903LS", "16", "", session=session)

    assert "2903LS" not in caplog.text
    assert "irado.nl" not in caplog.text


def test_irado_snippet_is_limited(caplog):
    """Only the start of a long body is logged."""
    session = FakeSession(FakeResponse("x" * 5000, content_type="text/html"))

    with pytest.raises(ValueError):
        irado.get_waste_data_raw("irado", "2903LS", "16", "", session=session)

    assert "x" * 200 in caplog.text
    assert "x" * 201 not in caplog.text
    assert "5000 bytes" in caplog.text


# --- provider, requests and errors ---------------------------------------------------


def _pickups(*items, valid=True):
    return {
        "valid": valid,
        "calendar_data": {"pickups": {"2026": {"11": {"13": list(items)}}}},
    }


def _item(date="13/11/2026", type_="gft"):
    return {"date": date, "type": type_}


def test_irado_refuses_an_unknown_provider():
    """Only listed providers have a URL."""
    with pytest.raises(ValueError, match="Invalid provider"):
        irado.get_waste_data_raw(
            "nonexistent", "2903LS", "16", "", session=FakeSession(FakeResponse())
        )


def test_irado_url_holds_the_postal_code_number_and_suffix():
    """The suffix goes into the extention parameter."""
    session = FakeSession(FakeResponse("{}", payload=PICKUPS))

    irado.get_waste_data_raw("irado", "2903 ls", "16", "B", session=session)

    assert "zipcode=2903LS&number=16&extention=B" in session.urls[0]


def test_irado_http_error_is_a_value_error_without_the_address():
    """The error describes the failure, not the address."""
    session = FakeSession(FakeResponse("", status_code=503))

    with pytest.raises(ValueError, match=r"request failed \(HTTPError 503\)") as raised:
        irado.get_waste_data_raw("irado", "2903LS", "16", "", session=session)
    assert "2903LS" not in str(raised.value)


def test_irado_empty_json_gives_no_pickups(caplog):
    """An empty JSON object is logged as no data."""
    session = FakeSession(FakeResponse("{}", payload={"unused": 1}))
    session.response._payload = {}

    assert irado.get_waste_data_raw("irado", "2903LS", "16", "", session=session) == []
    assert "No waste data found" in caplog.text


def test_irado_unknown_address_gives_no_pickups(caplog):
    """The API answers valid: false for an address it doesn't know."""
    session = FakeSession(FakeResponse("{}", payload={"valid": False}))

    assert irado.get_waste_data_raw("irado", "2903LS", "16", "", session=session) == []
    assert "Address not found" in caplog.text


@pytest.mark.parametrize(
    "payload", [{}, {"valid": False, "calendar_data": {"pickups": {}}}, None]
)
def test_parse_without_a_valid_answer_is_empty(payload):
    """Nothing valid, nothing parsed."""
    assert irado._parse_waste_data_raw(payload) == []


def test_parse_skips_everything_that_is_not_a_pickup():
    """Odd shapes at every level of year, month, day and item are ignored."""
    data = {
        "valid": True,
        "calendar_data": {
            "pickups": {
                "2026": {
                    "11": {
                        "13": [
                            "not a dict",
                            {"type": "gft"},
                            {"date": "13/11/2026"},
                            {"date": "13/11/2026", "type": "  "},
                            {"date": "13/11/2026", "type": None},
                            _item(type_="Papier "),
                        ],
                        "14": "not a list",
                    },
                    "12": "not a dict",
                },
                "2027": "not a dict",
            }
        },
    }

    assert irado._parse_waste_data_raw(data) == [
        {"type": "papier", "date": "2026-11-13"}
    ]


def test_parse_collects_pickups_over_years_months_and_days():
    """Every pickup in the nested calendar is returned."""
    data = {
        "valid": True,
        "calendar_data": {
            "pickups": {
                "2026": {"12": {"28": [_item("28/12/2026", "gft")]}},
                "2027": {
                    "1": {
                        "4": [_item("04/01/2027", "papier"), _item("04/01/2027", "pmd")]
                    }
                },
            }
        },
    }

    assert irado._parse_waste_data_raw(data) == [
        {"type": "gft", "date": "2026-12-28"},
        {"type": "papier", "date": "2027-01-04"},
        {"type": "pmd", "date": "2027-01-04"},
    ]


@pytest.mark.parametrize(
    "payload",
    [
        _pickups(_item(date="2026-11-13")),
        {"valid": True, "calendar_data": []},
        {"valid": True, "calendar_data": {"pickups": []}},
    ],
)
def test_irado_unreadable_data_is_a_value_error(payload):
    """A date in another format, or a changed structure, is invalid data."""
    session = FakeSession(FakeResponse("{}", payload=payload))

    with pytest.raises(ValueError, match="Invalid and/or no data received from Irado"):
        irado.get_waste_data_raw("irado", "2903LS", "16", "", session=session)
