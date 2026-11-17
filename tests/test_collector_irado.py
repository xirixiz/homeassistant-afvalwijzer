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
