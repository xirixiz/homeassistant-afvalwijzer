"""Tests for the Montferland collector (HTTPS app API, synthetic payloads)."""

from unittest.mock import Mock

import pytest
import requests

from custom_components.afvalwijzer.collector import montferland

BASE_URL = "https://montferlandapp-api-prod.azurewebsites.net"


def _response(data=None, status=200):
    response = Mock(spec=requests.Response)
    response.status_code = status
    response.json.return_value = data
    if status >= 400:
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(status)
    return response


def _session(response):
    session = Mock(spec=requests.Session)
    session.get.return_value = response
    return session


def _payload(items):
    return {"errorCode": 0, "errorMessage": None, "collections": items}


@pytest.mark.parametrize(
    ("suffix", "encoded"), [("", ""), (None, ""), ("A/B #", "A%2FB%20%23")]
)
def test_requests_https_api_without_redirects(suffix, encoded):
    """The address goes only to the HTTPS endpoint, with redirects disabled."""
    session = _session(_response(_payload([])))

    montferland.get_waste_data_raw(
        "montferland", "7041 ej", "13", suffix, session=session
    )

    session.get.assert_called_once()
    url = session.get.call_args.args[0]
    assert url == f"{BASE_URL}/api/v1/Garbage/7041EJ/13/{encoded}"
    kwargs = session.get.call_args.kwargs
    assert kwargs["allow_redirects"] is False
    assert kwargs["verify"] is True
    assert kwargs["headers"] == {"authToken": montferland._API_KEY}


def test_parses_fractions_and_drops_duplicates():
    """Known fractions map to standard waste types; duplicates and unknowns go."""
    items = [
        {"fraction": f, "collectionDate": f"2099-01-0{i + 1}T00:00:00"}
        for i, f in enumerate((1, 2, 3, 10))
    ]
    items += [*items, {"fraction": 999, "collectionDate": "2099-01-09T00:00:00"}]
    session = _session(_response(_payload(items)))

    result = montferland.get_waste_data_raw(
        "montferland", "7041EJ", "13", "", session=session
    )

    assert result == [
        {"type": "restafval", "date": "2099-01-01"},
        {"type": "gft", "date": "2099-01-02"},
        {"type": "papier", "date": "2099-01-03"},
        {"type": "pmd", "date": "2099-01-04"},
    ]


def test_empty_calendar_returns_empty_list():
    """A valid address without pickups yields no data rather than an error."""
    session = _session(_response(_payload([])))

    assert (
        montferland.get_waste_data_raw(
            "montferland", "7041EJ", "13", "", session=session
        )
        == []
    )


@pytest.mark.parametrize(
    "failure", ["tls", "redirect", "http", "json", "api", "missing", "date", "shape"]
)
def test_failures_raise_without_logging_address(caplog, failure):
    """Every failure raises ValueError, makes one request and keeps the address out of logs."""
    private = f"7041EJ {montferland._API_KEY}"
    response = _response(_payload([]))
    session = _session(response)

    if failure == "tls":
        session.get.side_effect = requests.exceptions.SSLError(private)
    elif failure == "redirect":
        response.status_code = 302
    elif failure == "http":
        response.status_code = 500
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(private)
    elif failure == "json":
        response.json.side_effect = requests.exceptions.JSONDecodeError(private, "", 0)
    elif failure == "api":
        response.json.return_value = {
            "errorCode": 2002,
            "errorMessage": "Ongeldig adres",
        }
    elif failure == "missing":
        response.json.return_value = {"errorCode": 0}
    elif failure == "date":
        response.json.return_value = _payload(
            [{"fraction": 1, "collectionDate": "invalid"}]
        )
    elif failure == "shape":
        response.json.return_value = _payload([None])

    with pytest.raises(ValueError):
        montferland.get_waste_data_raw(
            "montferland", "7041EJ", "13", "", session=session
        )

    session.get.assert_called_once()
    assert session.get.call_args.args[0].startswith("https://")
    assert "7041EJ" not in caplog.text
    assert montferland._API_KEY not in caplog.text


def test_invalid_provider():
    """An unknown provider is rejected before any request."""
    session = Mock(spec=requests.Session)

    with pytest.raises(ValueError):
        montferland.get_waste_data_raw("unknown", "7041EJ", "13", "", session=session)

    session.get.assert_not_called()
