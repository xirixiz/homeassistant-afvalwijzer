"""Afvalwijzer integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..common.main_functions import format_postal_code, waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_RD4

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)


def _build_url(provider: str, postal_code: str, street_number: str, suffix: str) -> str:
    if provider not in SENSOR_COLLECTORS_RD4:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    corrected_postal_code = format_postal_code(postal_code)
    year_current = datetime.now().year

    return SENSOR_COLLECTORS_RD4[provider].format(
        corrected_postal_code,
        street_number,
        suffix,
        year_current,
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
) -> list[dict[str, str]]:
    waste_data_raw: list[dict[str, str]] = []

    for item in waste_data_raw_temp:
        date_str = item.get("date")
        if not date_str:
            continue

        waste_type = waste_type_rename((item.get("type") or "").strip().lower())
        if not waste_type:
            continue

        waste_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
        waste_data_raw.append({"type": waste_type, "date": waste_date})

    return waste_data_raw


def get_waste_data_raw(
    provider: str,
    postal_code: str,
    street_number: str,
    suffix: str,
    *,
    session: requests.Session | None = None,
    timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
) -> list[dict[str, str]]:
    """Return waste_data_raw."""

    session = session or requests.Session()
    url = _build_url(provider, postal_code, street_number, suffix)

    try:
        waste_data_raw_temp = _fetch_waste_data_raw_temp(
            session,
            url,
            timeout=timeout,
            verify=verify,
        )

        if not waste_data_raw_temp:
            # Match original semantics: log based on likely cause
            # (If response empty or success false, caller expects [])
            _LOGGER.error("No waste data found or address not found!")
            return []

        waste_data_raw = _parse_waste_data_raw(waste_data_raw_temp)
        return waste_data_raw

    except requests.exceptions.RequestException as err:
        _LOGGER.error("RD4 request error: %s", err)
        raise ValueError(err) from err
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("RD4: Invalid and/or no data received from %s", url)
        raise ValueError(f"Invalid and/or no data received from {url}") from err
