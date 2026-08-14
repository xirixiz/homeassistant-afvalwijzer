"""Tests for the rd4 collector's HTTP handling."""

import pytest
import requests

from custom_components.afvalwijzer.collector import rd4


class _FakeResponse:
    """Minimal stand-in for a requests.Response."""

    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(
                f"{self.status_code} Client Error", response=self
            )


class _FakeSession:
    """Session that returns a canned response for any URL."""

    def __init__(self, response):
        self._response = response

    def get(self, url, timeout=None, verify=None):
        return self._response


def test_unknown_address_returns_empty_list():
    """RD4 answers an unknown address with 422; that is not-found, not an error."""
    session = _FakeSession(
        _FakeResponse(
            422,
            {
                "success": False,
                "code": 0,
                "message": "We kunnen geen adres vinden voor de ingevulde gegevens.",
                "data": [],
            },
        )
    )

    assert rd4.get_waste_data_raw("rd4", "6271EL", "32", "", session=session) == []


def test_server_error_still_raises():
    """Status codes other than 422 keep bubbling up as a ValueError."""
    session = _FakeSession(_FakeResponse(500, {}))

    with pytest.raises(ValueError):
        rd4.get_waste_data_raw("rd4", "6271EL", "30", "", session=session)


def test_valid_address_returns_parsed_entries():
    """A successful response is parsed into type/date pairs."""
    items = [
        {"date": "2026-01-05", "month": 1, "type": "residual_waste"},
        {"date": "2026-01-06", "month": 1, "type": "paper"},
    ]
    session = _FakeSession(
        _FakeResponse(200, {"success": True, "data": {"items": [items]}})
    )

    waste_data_raw = rd4.get_waste_data_raw("rd4", "6271EL", "30", "", session=session)

    assert [item["date"] for item in waste_data_raw] == ["2026-01-05", "2026-01-06"]
    assert all(item["type"] for item in waste_data_raw)
