"""Afvalwijzer reinis.

Reinis moved to the Scoop resident platform in November 2026. There is no
public address API anymore, but every address has a personal iCal feed:

1. ``/postcode`` sets the visitor's address through a Next.js server action.
   Its id is generated per build, so it is read from the page's JavaScript.
2. With the resulting session cookies, ``/api/proxy/pickups/ical-subscription``
   returns the address' iCal feed URL (with a long-lived token).
3. The feed itself needs no session and holds about a year of pickups.

The feed URL is cached per address, so steps 1 and 2 only run once per
Home Assistant start, or again when the cached feed URL stops working.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import requests

from ..common.main_functions import format_postal_code, parse_ical_waste_data
from ..const.const import SENSOR_COLLECTORS_REINIS

_LOGGER = logging.getLogger(__name__)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)

_POSTCODE_PATH = "/postcode?next=/kalender"
_ICAL_SUBSCRIPTION_PATH = "/api/proxy/pickups/ical-subscription"
_ADDRESS_ID_COOKIE = "scoop_address_id"

_CHUNK_PATTERN = re.compile(r"/_next/static/chunks/[\w.-]+\.js")
# The action id is a hex string passed to createServerReference next to the
# action's name; allow some slack in between for minifier changes.
_ACTION_ID_PATTERN = re.compile(
    r'"([0-9a-f]{40,})"[^"]{0,200}"ensureAnonSessionAction"'
)
_SUMMARY_SUFFIX_PATTERN = re.compile(r"\s+inzameling\s*$", re.IGNORECASE)

# (postal code, house number, suffix) -> iCal feed URL
_ICAL_URL_CACHE: dict[tuple[str, str, str], str] = {}


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
    """Set the visitor's address and return its Scoop address id, if known."""
    payload = [
        {
            "postcode": postal_code,
            "huisnummer": house_number,
            "toev": suffix or "$undefined",
        }
    ]
    response = session.post(
        f"{base_url}{_POSTCODE_PATH}",
        data=json.dumps(payload),
        headers={
            "Next-Action": action_id,
            "Content-Type": "text/plain;charset=UTF-8",
            "Accept": "text/x-component",
        },
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()
    return session.cookies.get(_ADDRESS_ID_COOKIE)


def _fetch_ical_url(
    session: requests.Session,
    base_url: str,
    address_id: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> str:
    response = session.get(
        f"{base_url}{_ICAL_SUBSCRIPTION_PATH}",
        params={"addressId": address_id},
        headers={"Accept": "application/json"},
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()
    data: dict[str, Any] = response.json() or {}
    url = (data.get("data") or {}).get("url") if data.get("ok") else None
    if not url:
        raise ValueError("Reinis: no iCal subscription URL received")
    return url


def _lookup_ical_url(
    session: requests.Session,
    base_url: str,
    postal_code: str,
    house_number: str,
    suffix: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> str | None:
    """Run the website flow and return the address' iCal feed URL."""
    action_id = _find_action_id(session, base_url, timeout=timeout, verify=verify)
    address_id = _set_address(
        session,
        base_url,
        action_id,
        postal_code=postal_code,
        house_number=house_number,
        suffix=suffix,
        timeout=timeout,
        verify=verify,
    )
    if not address_id:
        return None
    return _fetch_ical_url(
        session, base_url, address_id, timeout=timeout, verify=verify
    )


def _fetch_ical(
    session: requests.Session,
    url: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> str:
    response = session.get(url, timeout=timeout, verify=verify)
    response.raise_for_status()
    text = response.text or ""
    if "BEGIN:VCALENDAR" not in text:
        raise ValueError("Reinis: response is not an iCal feed")
    return text


def _normalize_summaries(ical_text: str) -> str:
    """Drop the " inzameling" suffix, so "GFT inzameling" maps to "gft"."""
    lines = []
    for line in ical_text.splitlines():
        if line.startswith("SUMMARY"):
            line = _SUMMARY_SUFFIX_PATTERN.sub("", line)
        lines.append(line)
    return "\n".join(lines)


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
        corrected_postal_code = format_postal_code(postal_code)
        suffix = (suffix or "").strip()
        cache_key = (corrected_postal_code, str(house_number), suffix.lower())

        ical_text = None
        if cached_url := _ICAL_URL_CACHE.get(cache_key):
            try:
                ical_text = _fetch_ical(
                    session, cached_url, timeout=timeout, verify=verify
                )
            except (requests.exceptions.RequestException, ValueError) as err:
                _LOGGER.debug(
                    "Reinis: cached iCal URL rejected (%s), looking up again", err
                )
                _ICAL_URL_CACHE.pop(cache_key, None)

        if ical_text is None:
            ical_url = _lookup_ical_url(
                session,
                base_url,
                corrected_postal_code,
                str(house_number),
                suffix,
                timeout=timeout,
                verify=verify,
            )
            if not ical_url:
                _LOGGER.error("Reinis: address not found!")
                return []
            ical_text = _fetch_ical(session, ical_url, timeout=timeout, verify=verify)
            _ICAL_URL_CACHE[cache_key] = ical_url

        waste_data_raw = parse_ical_waste_data(
            _normalize_summaries(ical_text), postal_code
        )
        if not waste_data_raw:
            # Addresses served by underground containers have no kerbside rounds.
            _LOGGER.warning(
                "Reinis: no kerbside pickups for this address (underground containers?)"
            )
        return waste_data_raw

    except requests.exceptions.RequestException as err:
        _LOGGER.error("Reinis request error: %s", err)
        raise ValueError(err) from err
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error(
            "Reinis: Invalid and/or no data received from %s: %s", base_url, err
        )
        raise ValueError(f"Invalid and/or no data received from {base_url}") from err
