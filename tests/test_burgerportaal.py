"""Tests for the Burgerportaal collector."""

from unittest.mock import Mock

import pytest
import requests

from custom_components.afvalwijzer.collector import burgerportaal


def _response(data=None, status=200, text=None):
    response = Mock(spec=requests.Response)
    response.status_code = status
    response.text = text if text is not None else "x"
    response.json.return_value = data
    if status >= 400:
        response.raise_for_status.side_effect = requests.exceptions.HTTPError(status)
    return response


@pytest.fixture(autouse=True)
def _clear_caches():
    """Keep the module-level id caches from leaking between tests."""
    burgerportaal._AUTH_CACHE.clear()
    burgerportaal._ADDRESS_ID_CACHE.clear()
    yield
    burgerportaal._AUTH_CACHE.clear()
    burgerportaal._ADDRESS_ID_CACHE.clear()


@pytest.fixture
def session():
    """Return a mocked session with a full happy-flow response sequence."""
    session = Mock(spec=requests.Session)
    session.post.side_effect = [
        _response({"refreshToken": "refresh"}),
        _response({"id_token": "token"}),
    ]
    session.get.side_effect = [
        _response([{"addressId": "address", "addition": ""}]),
        _response([{"fraction": "GFT", "collectionDate": "2099-01-02T00:00:00"}]),
    ]
    return session


def test_requests_send_custom_user_agent(session):
    """Every request identifies the integration."""
    result = burgerportaal.get_waste_data_raw(
        "assen", "1234AB", "1", "", session=session
    )

    assert len(result) == 1
    calls = session.post.call_args_list + session.get.call_args_list
    assert len(calls) == 4
    for call in calls:
        assert call.kwargs["headers"]["User-Agent"] == burgerportaal._USER_AGENT
    for call in session.get.call_args_list:
        assert call.kwargs["headers"]["authorization"] == "token"


def test_http_error_is_raised_as_value_error(session):
    """A blocked request raises instead of parsing the error body."""
    session.post.side_effect = [_response(status=403)]

    with pytest.raises(ValueError):
        burgerportaal.get_waste_data_raw("assen", "1234AB", "1", "", session=session)
    session.get.assert_not_called()
