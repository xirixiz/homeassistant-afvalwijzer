"""Tests for the Omrin collector."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import requests

from custom_components.afvalwijzer.collector import omrin


class FakeResponse:
    """Minimal requests.Response stand-in."""

    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        """Store the payload and status code."""
        self._payload = payload
        self.status_code = status_code
        self.content = b"x"

    def json(self) -> dict[str, Any]:
        """Return the payload."""
        return self._payload

    def raise_for_status(self) -> None:
        """Raise HTTPError for error statuses."""
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)


class FakeSession:
    """Session that replays queued responses per endpoint and records posts."""

    def __init__(self, responses: dict[str, list[FakeResponse]]) -> None:
        """Store the queued responses."""
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        """Record the call and return the next queued response."""
        endpoint = url.rsplit("omrinafvalapp.nl", 1)[1]
        self.calls.append((endpoint, kwargs))
        return self.responses[endpoint].pop(0)


def _login(token="tok", refresh="ref", expires="2999-01-01T00:00:00Z"):
    return FakeResponse(
        {
            "success": True,
            "data": {
                "accessToken": token,
                "refreshToken": refresh,
                "expiresAt": expires,
            },
        }
    )


def _calendar(*items):
    return FakeResponse({"data": {"fetchCalendar": list(items)}})


@pytest.fixture(autouse=True)
def _clear_auth_cache():
    omrin._AUTH_CACHE.clear()
    yield
    omrin._AUTH_CACHE.clear()


def _run(session, suffix=""):
    return omrin.get_waste_data_raw("omrin", "3844JP", "4", suffix, session=session)


def test_parses_iso_datetimes_and_skips_placeholder_dates():
    """ISO datetimes are parsed and placeholder dates skipped; "overig" without a known id is left as is."""
    session = FakeSession(
        {
            "/api/auth/login": [_login()],
            "/graphql": [
                _calendar(
                    {"date": "2026-03-04T00:00:00", "type": "GFT"},
                    {"date": "0001-01-01T00:00:00", "type": "PAPIER"},
                    {"date": "2026-03-05T00:00:00Z", "type": "OVERIG"},
                )
            ],
        }
    )

    assert _run(session) == [
        {"type": "gft", "date": "2026-03-04"},
        {"type": "overig", "date": "2026-03-05"},
    ]


def test_empty_suffix_is_sent_as_null():
    """An empty suffix is sent to the login endpoint as null."""
    session = FakeSession({"/api/auth/login": [_login()], "/graphql": [_calendar()]})

    _run(session)

    login_payload = session.calls[0][1]["json"]
    assert login_payload["HouseNumberExtension"] is None


def test_second_refresh_reuses_cached_token_and_device_id():
    """A second refresh reuses the cached token instead of logging in again."""
    session = FakeSession(
        {
            "/api/auth/login": [_login()],
            "/graphql": [_calendar(), _calendar()],
        }
    )

    _run(session)
    _run(session)

    endpoints = [endpoint for endpoint, _ in session.calls]
    assert endpoints == ["/api/auth/login", "/graphql", "/graphql"]


def test_expiring_token_is_refreshed():
    """A token that is about to expire is refreshed with the refresh token."""
    soon = (datetime.now(UTC) + timedelta(seconds=10)).isoformat()
    session = FakeSession(
        {
            "/api/auth/login": [_login(expires=soon)],
            "/api/auth/refreshtoken": [_login(token="tok2", refresh="ref2")],
            "/graphql": [_calendar(), _calendar()],
        }
    )

    _run(session)
    _run(session)

    endpoints = [endpoint for endpoint, _ in session.calls]
    assert endpoints == [
        "/api/auth/login",
        "/graphql",
        "/api/auth/refreshtoken",
        "/graphql",
    ]
    assert session.calls[2][1]["json"] == {"Token": "tok", "RefreshToken": "ref"}
    assert session.calls[3][1]["headers"]["Authorization"] == "Bearer tok2"


def test_rejected_refresh_token_falls_back_to_login():
    """A rejected refresh token leads to a new login on the same device."""
    soon = (datetime.now(UTC) + timedelta(seconds=10)).isoformat()
    session = FakeSession(
        {
            "/api/auth/login": [_login(expires=soon), _login(token="tok3")],
            "/api/auth/refreshtoken": [FakeResponse({}, status_code=401)],
            "/graphql": [_calendar(), _calendar()],
        }
    )

    _run(session)
    _run(session)

    first_device = session.calls[0][1]["json"]["DeviceId"]
    relogin = [c for c in session.calls if c[0] == "/api/auth/login"][1][1]["json"]
    assert relogin["DeviceId"] == first_device
    assert session.calls[-1][1]["headers"]["Authorization"] == "Bearer tok3"


def test_rejected_access_token_logs_in_again_once():
    """A 401 on the calendar call logs in again and retries once."""
    session = FakeSession(
        {
            "/api/auth/login": [_login(), _login(token="tok2")],
            "/graphql": [
                FakeResponse({}, status_code=401),
                _calendar({"date": "2026-03-04T00:00:00", "type": "GFT"}),
            ],
        }
    )

    assert _run(session) == [{"type": "gft", "date": "2026-03-04"}]
    assert session.calls[-1][1]["headers"]["Authorization"] == "Bearer tok2"


@pytest.mark.parametrize(
    ("stream_id", "expected"),
    [
        ("f08536f9-9190-4b1c-970c-c0166b297cc5", "kerstbomen"),
        ("3b3c91d7-79e1-423e-a948-ae5bb6be7ce7", "kca"),
        ("9a914aa8-3d75-4d00-9aa7-ccce91332a7e", "snoeiafval"),
        ("C54D0705-1594-4BD4-93F6-6321932C21DB", "elektrische-apparaten"),
        ("00000000-0000-0000-0000-000000000000", "overig"),
        (None, "overig"),
    ],
)
def test_overig_is_resolved_through_its_id(stream_id, expected):
    """The catch-all type "overig" becomes the stream its id names."""
    item = {"id": stream_id, "date": "2026-01-14", "type": "OVERIG"}

    assert omrin._parse_waste_data_raw([item]) == [
        {"type": expected, "date": "2026-01-14"}
    ]


def test_overig_ignores_the_description():
    """A changed or misleading description doesn't influence the result."""
    item = {
        "id": "3b3c91d7-79e1-423e-a948-ae5bb6be7ce7",
        "date": "2026-01-14",
        "type": "OVERIG",
        "description": "Heel andere tekst over kerstbomen",
    }

    assert omrin._parse_waste_data_raw([item]) == [
        {"type": "kca", "date": "2026-01-14"}
    ]


def test_other_types_ignore_the_id():
    """Only "overig" is resolved through the id."""
    item = {
        "id": "3b3c91d7-79e1-423e-a948-ae5bb6be7ce7",
        "date": "2026-01-14",
        "type": "RESTAFVAL",
    }

    assert omrin._parse_waste_data_raw([item]) == [
        {"type": "restafval", "date": "2026-01-14"}
    ]


def test_entries_without_a_date_are_skipped():
    """Public containers come without date or description."""
    item = {"date": None, "type": "PAPIER", "description": None}

    assert omrin._parse_waste_data_raw([item]) == []
