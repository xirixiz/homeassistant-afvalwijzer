"""Afvalwijzer reinis.

Reinis moved to the Scoop resident platform in November 2026. There is no
public address API anymore, so this follows what the website does:

1. ``/postcode`` sets the visitor's address through a Next.js server action and
   starts an anonymous session (cookies). The action's id is generated per
   build, so it is read from the page's JavaScript.
2. With that session, ``/api/proxy/pickups/calendar`` returns the pickups for a
   date range as JSON (the API accepts up to 366 days).

The session's access cookie only lives for an hour, so a new session is started on
every refresh. The action id is kept in memory, so a refresh is two requests; it is
looked up again when a request with it fails (a new build of the website).
"""

from __future__ import annotations

from datetime import date, timedelta
import json
import logging
import re
from typing import Any

import requests

from ..common.main_functions import format_postal_code, waste_type_rename
from ..const.const import SENSOR_COLLECTORS_REINIS

_LOGGER = logging.getLogger(__name__)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)

_POSTCODE_PATH = "/postcode?next=/kalender"
_CALENDAR_PATH = "/api/proxy/pickups/calendar"
# 365 days between the endpoints stays within the API's 366-day limit, also when
# both endpoints are counted.
_CALENDAR_DAYS = 365

_CHUNK_PATTERN = re.compile(r"/_next/static/chunks/[\w.-]+\.js")
# The action id is a hex string passed to createServerReference next to the
# action's name; allow some slack in between for minifier changes.
_ACTION_ID_PATTERN = re.compile(
    r'"([0-9a-f]{40,})"[^"]{0,200}"ensureAnonSessionAction"'
)
# Next.js answers an unknown action id with one of these.
_STALE_ACTION_STATUS = (400, 404, 405)

# base URL -> id of the server action that sets the visitor's address
_ACTION_ID_CACHE: dict[str, str] = {}


class _StaleActionError(ValueError):
    """The cached server action id no longer works (a new build of the website)."""


def _build_base_url(provider: str) -> str:
    if provider not in SENSOR_COLLECTORS_REINIS:
        raise ValueError(f"Invalid provider: {provider}, please verify")
    return SENSOR_COLLECTORS_REINIS[provider]


def _find_action_id(
    session: requests.Session,
    base_url: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> str:
    """Return the id of the server action that sets the visitor's address."""
    response = session.get(
        f"{base_url}{_POSTCODE_PATH}", timeout=timeout, verify=verify
    )
    response.raise_for_status()

    # Page-specific chunks come last, so search from the end.
    chunks = list(dict.fromkeys(_CHUNK_PATTERN.findall(response.text)))
    for chunk in reversed(chunks):
        chunk_response = session.get(
            f"{base_url}{chunk}", timeout=timeout, verify=verify
        )
        if not chunk_response.ok:
            continue
        if match := _ACTION_ID_PATTERN.search(chunk_response.text):
            return match.group(1)

    raise ValueError("Reinis: could not find the address action on the website")


def _action_result(text: str) -> dict[str, Any] | None:
    """Return the server action's result from its React Server Components answer."""
    for line in text.splitlines():
        _, _, value = line.partition(":")
        if not value.startswith("{"):
            continue
        try:
            result = json.loads(value)
        except ValueError:
            continue
        if isinstance(result, dict) and "ok" in result:
            return result
    return None


def _set_address(
    session: requests.Session,
    base_url: str,
    action_id: str,
    *,
    postal_code: str,
    house_number: str,
    suffix: str,
    timeout: tuple[float, float],
    verify: bool,
) -> str | None:
    """Set the visitor's address and return its Scoop address id (None: unknown)."""
    response = session.post(
        f"{base_url}{_POSTCODE_PATH}",
        data=json.dumps(
            [
                {
                    "postcode": postal_code,
                    "huisnummer": house_number,
                    "toev": suffix or "$undefined",
                }
            ]
        ),
        headers={
            "Next-Action": action_id,
            "Content-Type": "text/plain;charset=UTF-8",
            "Accept": "text/x-component",
        },
        timeout=timeout,
        verify=verify,
    )
    if response.status_code in _STALE_ACTION_STATUS:
        raise _StaleActionError("Reinis: the address action was rejected")
    response.raise_for_status()

    result = _action_result(response.text)
    if result is None:
        raise _StaleActionError("Reinis: no answer from the address action")
    if result.get("ok") is not True:
        # e.g. "ADDRESS_NOT_FOUND"
        _LOGGER.error("Reinis did not accept the address: %s", result.get("error"))
        return None
    return result["data"]["addressId"]


def _lookup_address_id(
    session: requests.Session,
    base_url: str,
    *,
    postal_code: str,
    house_number: str,
    suffix: str,
    timeout: tuple[float, float],
    verify: bool,
) -> str | None:
    """Start the session for an address and return its Scoop address id.

    Uses the remembered action id, and looks it up again when that no longer works.
    """
    options = {
        "postal_code": postal_code,
        "house_number": house_number,
        "suffix": suffix,
        "timeout": timeout,
        "verify": verify,
    }
    if cached_action_id := _ACTION_ID_CACHE.get(base_url):
        try:
            return _set_address(session, base_url, cached_action_id, **options)
        except _StaleActionError:
            _LOGGER.debug("Reinis: the address action is stale, looking it up again")
            _ACTION_ID_CACHE.pop(base_url, None)

    action_id = _find_action_id(session, base_url, timeout=timeout, verify=verify)
    address_id = _set_address(session, base_url, action_id, **options)
    _ACTION_ID_CACHE[base_url] = action_id
    return address_id


def _fetch_calendar(
    session: requests.Session,
    base_url: str,
    address_id: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> list[dict[str, Any]]:
    """Return the calendar's days: [{"date": ..., "pickups": [...]}, ...]."""
    today = date.today()
    response = session.get(
        f"{base_url}{_CALENDAR_PATH}",
        params={
            "addressId": address_id,
            "from": today.isoformat(),
            "to": (today + timedelta(days=_CALENDAR_DAYS)).isoformat(),
        },
        headers={"Accept": "application/json"},
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise ValueError("Reinis: no calendar received")
    days = (payload.get("data") or {}).get("days")
    if not isinstance(days, list):
        raise TypeError("Reinis: invalid calendar days")
    return days


def _parse_waste_data_raw(
    days: list[dict[str, Any]], postal_code: str = ""
) -> list[dict[str, str]]:
    waste_data_raw: list[dict[str, str]] = []

    for day in days:
        for pickup in (day or {}).get("pickups") or []:
            pickup_date = (pickup or {}).get("date")
            stream = ((pickup or {}).get("streamId") or "").strip().lower()
            if not pickup_date or not stream:
                continue

            waste_type = waste_type_rename(stream, postal_code)
            if not waste_type:
                continue

            waste_data_raw.append({"type": waste_type, "date": pickup_date})

    return waste_data_raw


def get_waste_data_raw(
    provider: str,
    postal_code: str,
    house_number: str,
    suffix: str = "",
    *,
    session: requests.Session | None = None,
    timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = True,
) -> list[dict[str, str]]:
    """Return waste_data_raw."""

    session = session or requests.Session()
    base_url = _build_base_url(provider)

    try:
        address_id = _lookup_address_id(
            session,
            base_url,
            postal_code=format_postal_code(postal_code),
            house_number=str(house_number),
            suffix=(suffix or "").strip(),
            timeout=timeout,
            verify=verify,
        )
        if not address_id:
            return []

        days = _fetch_calendar(
            session, base_url, address_id, timeout=timeout, verify=verify
        )
        waste_data_raw = _parse_waste_data_raw(days, postal_code)
        if not waste_data_raw:
            # Addresses served by underground containers have no kerbside rounds.
            _LOGGER.warning(
                "Reinis: no kerbside pickups for this address (underground containers?)"
            )
        return waste_data_raw

    except requests.exceptions.RequestException as err:
        # The error message holds the request URL, so log the type and status only.
        status = getattr(err.response, "status_code", None)
        detail = f"{type(err).__name__}{f' {status}' if status else ''}"
        _LOGGER.error("Reinis request error (%s)", detail)
        raise ValueError(f"Reinis request failed ({detail})") from err
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("Reinis: invalid and/or no data received (%s)", err)
        raise ValueError(f"Invalid and/or no data received from {base_url}") from err
