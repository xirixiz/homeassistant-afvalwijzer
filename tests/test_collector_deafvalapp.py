"""Tests for the DeAfvalApp collector transport security."""

from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from custom_components.afvalwijzer.collector import deafvalapp


def _session(status=200, text="rest;01-01-2099;\n"):
    response = Mock(spec=requests.Response)
    response.status_code = status
    response.text = text
    response.headers = {"Location": "http://dataservice.deafvalapp.nl/"}
    if status >= 400:
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(status)
    session = Mock(spec=requests.Session)
    session.get.return_value = response
    return session


def test_uses_https_without_redirects():
    """The address goes only to the HTTPS endpoint, with redirects disabled."""
    session = _session()

    result = deafvalapp.get_waste_data_raw(
        "deafvalapp", "1234AB", "1", "A", session=session
    )

    url = urlsplit(session.get.call_args.args[0])
    assert url.scheme == "https"
    assert url.netloc == "dataservice.deafvalapp.nl"
    assert parse_qs(url.query)["postcode"] == ["1234AB"]
    assert session.get.call_args.kwargs["allow_redirects"] is False
    assert result == [{"type": "restafval", "date": "2099-01-01"}]


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308, 500])
def test_rejects_redirects_and_http_errors(status):
    """Redirects are not followed and failed responses are not parsed."""
    session = _session(status=status)

    with pytest.raises(ValueError):
        deafvalapp.get_waste_data_raw("deafvalapp", "1234AB", "1", "", session=session)

    session.get.assert_called_once()


def test_no_http_fallback_after_tls_failure():
    """A TLS failure is not retried over plain HTTP."""
    session = _session()
    session.get.side_effect = requests.exceptions.SSLError("invalid certificate")

    with pytest.raises(ValueError):
        deafvalapp.get_waste_data_raw("deafvalapp", "1234AB", "1", "", session=session)

    session.get.assert_called_once()
    assert session.get.call_args.args[0].startswith("https://")
