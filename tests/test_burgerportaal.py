"""Tests for the Burgerportaal collector edge cases."""

from unittest.mock import MagicMock

import pytest
import requests

from custom_components.afvalwijzer.collector import burgerportaal
from custom_components.afvalwijzer.const.const import SENSOR_COLLECTORS_BURGERPORTAAL

_TIMEOUT = (1.0, 1.0)


def _response(status_code=200, text="[]", json_data=None):
    response = MagicMock()
    response.status_code = status_code
    response.text = text
    response.json.return_value = json_data
    response.raise_for_status.return_value = None
    return response


def test_breda_is_registered():
    """Breda uses the Burgerportaal organisation id."""
    assert SENSOR_COLLECTORS_BURGERPORTAAL["breda"] == "452048812597352613"


@pytest.mark.parametrize(("status_code", "text"), [(204, ""), (200, "")])
def test_empty_calendar_returns_no_data(status_code, text):
    """An empty calendar response (HTTP 204) is not an error."""
    session = MagicMock()
    session.get.return_value = _response(status_code, text)
    result = burgerportaal._fetch_waste_data_raw_temp(
        session, "org", "addr", "token", timeout=_TIMEOUT, verify=True
    )
    assert result == []


def test_empty_address_lookup_returns_no_data():
    """An empty address lookup (HTTP 204) is not an error."""
    session = MagicMock()
    session.get.return_value = _response(204, "")
    result = burgerportaal._fetch_address_list(
        session, "org", "4811AA", "2", "token", timeout=_TIMEOUT, verify=True
    )
    assert result == []


def test_rejected_refresh_token_requests_new_credentials():
    """A rejected stored refresh token falls back to a new anonymous signup."""
    session = MagicMock()
    rejected = _response(400, '{"error":{}}')
    rejected.raise_for_status.side_effect = requests.exceptions.HTTPError("400")
    signup = _response(200, "{}", {"refreshToken": "new-refresh"})
    refreshed = _response(200, "{}", {"id_token": "new-id"})
    session.post.side_effect = [rejected, signup, refreshed]

    id_token, refresh_token = burgerportaal._get_auth_token(
        session, timeout=_TIMEOUT, verify=True, refresh_token="stale"
    )

    assert (id_token, refresh_token) == ("new-id", "new-refresh")


def test_breda_fractions_are_mapped():
    """The Breda fractions map to the standard waste types."""
    raw = [
        {"collectionDate": "2026-10-09T00:00:00.000Z", "fraction": "GFT+E"},
        {"collectionDate": "2026-10-12T00:00:00.000Z", "fraction": "OPK"},
        {"collectionDate": "2026-10-13T00:00:00.000Z", "fraction": "PBD"},
    ]
    result = burgerportaal._parse_waste_data_raw(raw, "4817XH")
    assert [r["type"] for r in result] == ["gft", "papier", "pmd"]
