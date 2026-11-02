"""Afvalwijzer montferland.

Uses the HTTPS API behind the Montferland municipality app. The legacy
afvaloverzicht.nl API only spoke plain HTTP, which sent the address and a
shared login in cleartext.
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any
from urllib.parse import quote

import requests

from ..common.main_functions import format_postal_code, waste_type_rename
from ..const.const import SENSOR_COLLECTORS_MONTFERLAND

_LOGGER = logging.getLogger(__name__)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)

# Shared application token shipped with the Montferland Android app.
_API_KEY = "77FE5F8B-9051-4B05-A525-C7CCCD42236F"

# The app API returns numeric fractions; map them to labels that
# waste_type_rename turns into the standard waste types.
_FRACTIONS: dict[int, str] = {
    1: "Restafval",
    2: "GFT",
    3: "Papier",
    10: "PMD",
}


def _build_url(provider: str, postal_code: str, house_number: str, suffix: str) -> str:
    """Build the garbage URL for an address."""
    url = SENSOR_COLLECTORS_MONTFERLAND.get(provider)
    if not url:
        raise ValueError(f"Invalid provider: {provider}, please verify")
    path = "/".join(
        quote(str(part), safe="") for part in (postal_code, house_number, suffix)
    )
    return f"{url.rstrip('/')}/api/v1/Garbage/{path}"


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    url: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> dict[str, Any]:
    response = session.get(
        url,
        headers={"authToken": _API_KEY},
        timeout=timeout,
        verify=verify,
        # Never follow a redirect that could send the address over plain HTTP.
        allow_redirects=False,
    )
    if 300 <= response.status_code < 400:
        raise requests.exceptions.RequestException(
            "MONTFERLAND returned an unexpected redirect"
        )
    response.raise_for_status()
    return response.json()


def _parse_waste_data_raw(
    waste_data_raw_temp: dict[str, Any],
    postal_code: str = "",
) -> list[dict[str, str]]:
    if not isinstance(waste_data_raw_temp, dict):
        raise TypeError("Unexpected response")

    error_code = waste_data_raw_temp.get("errorCode")
    if error_code != 0:
        raise ValueError(
            f"API error {error_code}: {waste_data_raw_temp.get('errorMessage')}"
        )

    items = waste_data_raw_temp.get("collections")
    if not isinstance(items, list):
        raise TypeError("Missing collections")

    waste_data_raw: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for item in items:
        label = _FRACTIONS.get(item.get("fraction"))
        if label is None:
            _LOGGER.debug("MONTFERLAND: skipping unknown fraction %s", item)
            continue

        date_str = item.get("collectionDate")
        if not date_str:
            continue

        waste_type = waste_type_rename(label, postal_code)
        if not waste_type:
            continue

        waste_date = datetime.fromisoformat(date_str).strftime("%Y-%m-%d")
        key = (waste_type, waste_date)
        if key in seen:
            continue
        seen.add(key)
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
    suffix = (suffix or "").strip()
    postal_code = format_postal_code(postal_code)

    try:
        url = _build_url(provider, postal_code, str(house_number), suffix)
        waste_data_raw_temp = _fetch_waste_data_raw_temp(
            session, url, timeout=timeout, verify=verify
        )
    except requests.exceptions.RequestException as err:
        # Request errors can include the address URL; log only the type.
        _LOGGER.error("MONTFERLAND request error (%s)", type(err).__name__)
        raise ValueError(err) from err

    try:
        waste_data_raw = _parse_waste_data_raw(waste_data_raw_temp, postal_code)
    except (AttributeError, KeyError, TypeError, ValueError) as err:
        _LOGGER.error("MONTFERLAND: Invalid and/or no data received (%s)", err)
        raise ValueError("Invalid and/or no data received from MONTFERLAND") from err

    if not waste_data_raw:
        _LOGGER.error("No Waste data found!")

    return waste_data_raw
