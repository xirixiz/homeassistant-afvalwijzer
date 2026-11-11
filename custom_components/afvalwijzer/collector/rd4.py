"""Afvalwijzer rd4."""

from __future__ import annotations

from datetime import datetime
from html import unescape
import logging
import re
from typing import Any

import requests

from ..common.main_functions import format_postal_code, waste_type_rename
from ..const.const import SENSOR_COLLECTORS_RD4

_LOGGER = logging.getLogger(__name__)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)


def _build_url(
    provider: str, postal_code: str, house_number: str, suffix: str, year: int
) -> str:
    if provider not in SENSOR_COLLECTORS_RD4:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    corrected_postal_code = format_postal_code(postal_code)

    return SENSOR_COLLECTORS_RD4[provider].format(
        corrected_postal_code,
        house_number,
        suffix,
        year,
    )


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    url: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> list[dict[str, Any]]:
    response = session.get(url, timeout=timeout, verify=verify)
    response.raise_for_status()
    data = response.json() or {}

    if not data:
        return []

    if not data.get("success"):
        # Keep original behavior: treat as address-not-found
        return []

    # Original: response["data"]["items"][0] is expected to be an iterable of entries
    items = (((data.get("data") or {}).get("items") or [])[:1] or [None])[0]
    return items or []


def _parse_waste_data_raw(
    waste_data_raw_temp: list[dict[str, Any]],
    postal_code: str = "",
) -> list[dict[str, str]]:
    waste_data_raw: list[dict[str, str]] = []

    for item in waste_data_raw_temp:
        date_str = item.get("date")
        if not date_str:
            continue

        waste_type = waste_type_rename(
            (item.get("type") or "").strip().lower(), postal_code
        )
        if not waste_type:
            continue

        waste_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
        waste_data_raw.append({"type": waste_type, "date": waste_date})

    return waste_data_raw


def get_waste_data_raw(
    provider: str,
    postal_code: str,
    house_number: str,
    suffix: str,
    *,
    session: requests.Session | None = None,
    timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = True,
) -> list[dict[str, str]]:
    """Return waste_data_raw."""

    session = session or requests.Session()
    current_year = datetime.now().year
    url = _build_url(provider, postal_code, house_number, suffix, current_year)

    try:
        waste_data_raw_temp = _fetch_waste_data_raw_temp(
            session,
            url,
            timeout=timeout,
            verify=verify,
        )

        # Also fetch next year, so the schedule does not run dry at the end of the
        # year. Next year's calendar may not be published yet, so failures are ignored.
        next_url = _build_url(
            provider, postal_code, house_number, suffix, current_year + 1
        )
        try:
            waste_data_raw_temp = waste_data_raw_temp + _fetch_waste_data_raw_temp(
                session,
                next_url,
                timeout=timeout,
                verify=verify,
            )
        except (requests.exceptions.RequestException, ValueError, TypeError) as err:
            _LOGGER.debug("RD4: no data for %s: %s", current_year + 1, err)

        if not waste_data_raw_temp:
            # Match original semantics: log based on likely cause
            # (If response empty or success false, caller expects [])
            _LOGGER.error("No waste data found or address not found!")
            return []

        waste_data_raw = _parse_waste_data_raw(waste_data_raw_temp, postal_code)
        return waste_data_raw

    except requests.exceptions.RequestException as err:
        _LOGGER.error("RD4 request error: %s", err)
        raise ValueError(err) from err
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("RD4: Invalid and/or no data received from %s", url)
        raise ValueError(f"Invalid and/or no data received from {url}") from err


# Notifications come from the app API (v2), not from the calendar API (v1). It
# accepts an address-only session, just like the RD4 app does before linking a
# waste card, and validates X-Rd4-Client against the app's own client id.
_APP_API_URL = "https://data.rd4.nl/api/v2"
_APP_CLIENT = "android/app.rd4.nl/4.6.2"
_USER_AGENT = "homeassistant-afvalwijzer"
# "personal-news" is a message for this address, "news" one for everybody.
# "waste-calendar" reminders duplicate the calendar, "ticket" needs an account.
_NOTIFICATION_TYPES = ("personal-news", "news")


def _app_headers(token: str | None = None) -> dict[str, str]:
    headers = {
        "X-Rd4-Client": _APP_CLIENT,
        "User-Agent": _USER_AGENT,
        "Accept-Language": "nl-NL",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _app_data(response: requests.Response) -> Any:
    """Return the payload of an app API response (wrapped in "data" or not)."""
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict) and "data" in payload:
        return payload["data"]
    return payload


def _start_app_session(
    session: requests.Session,
    postal_code: str,
    house_number: int,
    suffix: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> str | None:
    """Start an address-only app session and return its token."""
    response = session.post(
        f"{_APP_API_URL}/auth/session",
        json={
            "type": "waste-card",
            "postalCode": postal_code,
            "houseNr": house_number,
            "houseNrExt": suffix,
            "wasteCardNr": None,
        },
        headers=_app_headers(),
        timeout=timeout,
        verify=verify,
    )
    data = _app_data(response)
    return data.get("authToken") if isinstance(data, dict) else None


def _fetch_notifications(
    session: requests.Session,
    token: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> list[dict[str, Any]]:
    response = session.get(
        f"{_APP_API_URL}/notifications",
        # One page (the app uses the same cursor-based Page) is plenty for an inbox.
        params={"types[]": list(_NOTIFICATION_TYPES), "limit": 50},
        headers=_app_headers(token),
        timeout=timeout,
        verify=verify,
    )
    data = _app_data(response)
    if isinstance(data, dict):
        data = data.get("items", [])
    return data if isinstance(data, list) else []


def _parse_notifications(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    notifications: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict) or item.get("type") not in _NOTIFICATION_TYPES:
            continue
        title = unescape(re.sub(r"<[^>]*>", "", item.get("title") or "")).strip()
        content = unescape(
            re.sub(r"<[^>]*>", "", item.get("description") or "")
        ).strip()
        if not title and not content:
            continue
        notifications.append(
            {
                "id": item.get("id"),
                "type": item["type"],
                "title": title,
                "content": content,
                "date": item.get("date"),
                "dismissable": False,
            }
        )
    return notifications


def get_notification_data_raw(
    provider: str,
    postal_code: str,
    house_number: str,
    suffix: str = "",
    *,
    session: requests.Session | None = None,
    timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = True,
) -> list[dict[str, Any]]:
    """Return the RD4 app messages for this address."""
    if provider not in SENSOR_COLLECTORS_RD4:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    session = session or requests.Session()
    try:
        house_number_int = int(str(house_number).strip())
    except ValueError:
        _LOGGER.debug(
            "RD4: house number %r is not numeric, no notifications", house_number
        )
        return []

    try:
        token = _start_app_session(
            session,
            format_postal_code(postal_code),
            house_number_int,
            (suffix or "").strip().upper(),
            timeout=timeout,
            verify=verify,
        )
        if not token:
            _LOGGER.debug("RD4: no app session for this address, no notifications")
            return []
        return _parse_notifications(
            _fetch_notifications(session, token, timeout=timeout, verify=verify)
        )
    except requests.exceptions.RequestException as err:
        # The error may carry the session token in its request, so log the type only.
        _LOGGER.warning("RD4: could not fetch notifications (%s)", type(err).__name__)
        return []
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.warning("RD4: invalid notification data (%s)", type(err).__name__)
        return []
