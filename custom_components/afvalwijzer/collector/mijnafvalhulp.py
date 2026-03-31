"""Afvalwijzer integration - mijnafvalhulp collector."""

from __future__ import annotations

import re

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..common.main_functions import format_postal_code, parse_ical_waste_data
from ..const.const import _LOGGER, SENSOR_COLLECTORS_MIJNAFVALHULP

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)


def _build_url(provider: str) -> str:
    """Build the base URL for the mijnafvalhulp collector."""
    url = SENSOR_COLLECTORS_MIJNAFVALHULP.get(provider)
    if not url:
        raise ValueError(f"Invalid provider: {provider}, please verify")
    return url


def _get_csrf_token(html: str) -> str | None:
    """Extract CSRF token from HTML."""
    match = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
    if match:
        return match.group(1)
    match = re.search(r'name="_token"\s+value="([^"]+)"', html)
    return match.group(1) if match else None


def _get_ical_url(html: str) -> str:
    """Extract iCal URL from the schedule page HTML."""
    match = re.search(
        r"https://mijn\.afvalhulp\.nl/api/v1/ical/[a-f0-9-]{36}/calendar\.ics",
        html,
    )
    if not match:
        raise ValueError(
            "Could not find iCal URL in mijnafvalhulp page — login may have failed"
        )
    return match.group(0)


def _fetch_waste_data_raw(
    session: requests.Session,
    url: str,
    postal_code: str,
    house_number: str,
    suffix: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> str:
    """Login to mijnafvalhulp and return raw iCal content."""
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"{url}/",
    }

    form_page = session.get(f"{url}/postcode", headers=headers, timeout=timeout)
    form_page.raise_for_status()

    token = _get_csrf_token(form_page.text)
    if not token:
        raise ValueError("Could not find CSRF token in mijnafvalhulp login page")

    payload = {
        "_token": token,
        "postcode": format_postal_code(postal_code),
        "housenumber": house_number,
        "addition": suffix or "",
    }

    result = session.post(
        f"{url}/postcode",
        data=payload,
        headers=headers,
        timeout=timeout,
        allow_redirects=True,
    )
    result.raise_for_status()

    schedule_page = session.get(
        f"{url}/pickup-schedule",
        headers={**headers, "Referer": result.url},
        timeout=timeout,
    )
    schedule_page.raise_for_status()
    ical_url = _get_ical_url(schedule_page.text)

    ical_response = session.get(ical_url, headers=headers, timeout=timeout)
    ical_response.raise_for_status()

    return ical_response.text or ""


def get_waste_data_raw(
    provider: str,
    postal_code: str,
    house_number: str,
    suffix: str,
    *,
    session: requests.Session | None = None,
    timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
) -> list[dict[str, str]]:
    """Return waste_data_raw for mijnafvalhulp."""

    session = session or requests.Session()

    url = _build_url(provider)

    try:
        waste_data_raw_temp = _fetch_waste_data_raw(
            session,
            url,
            postal_code,
            house_number,
            suffix,
            timeout=timeout,
            verify=verify,
        )
    except requests.exceptions.RequestException as err:
        _LOGGER.error("mijnafvalhulp request error: %s", err)
        raise ValueError(err) from err

    if not waste_data_raw_temp:
        _LOGGER.error("No waste data found for mijnafvalhulp!")
        return []

    try:
        waste_data_raw = parse_ical_waste_data(waste_data_raw_temp, postal_code)
        return waste_data_raw
    except (ValueError, KeyError) as err:
        _LOGGER.error("mijnafvalhulp: invalid or no data received")
        raise ValueError("mijnafvalhulp: invalid or no data received") from err
