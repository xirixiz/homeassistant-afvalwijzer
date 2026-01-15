"""Afvalwijzer integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..common.main_functions import format_postal_code, waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_IRADO

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)

_DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}


def _build_url(provider: str, postal_code: str, street_number: str, suffix: str) -> str:
    if provider not in SENSOR_COLLECTORS_IRADO:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    corrected_postal_code = format_postal_code(postal_code)

    return SENSOR_COLLECTORS_IRADO[provider].format(
        corrected_postal_code,
        street_number,
        suffix,
    )


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    url: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> dict[str, Any]:
    raw_response = session.get(
        url,
        headers=_DEFAULT_HEADERS,
        timeout=timeout,
        verify=verify,
    )
    raw_response.raise_for_status()
    return raw_response.json()


def _parse_waste_data_raw(waste_data_raw_temp: dict[str, Any]) -> list[dict[str, str]]:
    if not waste_data_raw_temp:
        return []

    if not waste_data_raw_temp.get("valid", False):
        return []

    pickups = waste_data_raw_temp.get("calendar_data", {}).get("pickups", {})

    waste_data_raw: list[dict[str, str]] = []

    # Structure: {year: {month: {day: [ {date,type,...}, ... ]}}}
    for months in pickups.values():
        if not isinstance(months, dict):
            continue

        for days in months.values():
            if not isinstance(days, dict):
                continue

            for items in days.values():
                if not isinstance(items, list):
                    continue

                for item in items:
                    if not isinstance(item, dict):
                        continue

                    date_str = item.get("date")
                    if not date_str:
                        continue

                    waste_type_raw = (item.get("type") or "").strip().lower()
                    if not waste_type_raw:
                        continue

                    waste_type = waste_type_rename(waste_type_raw)
                    if not waste_type:
                        continue

                    waste_date = datetime.strptime(date_str, "%d/%m/%Y").strftime(
                        "%Y-%m-%d"
                    )
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
    except requests.exceptions.RequestException as err:
        _LOGGER.error("Irado request error: %s", err)
        raise ValueError(err) from err

    if not waste_data_raw_temp:
        _LOGGER.error("No waste data found!")
        return []

    if not waste_data_raw_temp.get("valid", False):
        _LOGGER.error("Address not found!")
        return []

    try:
        waste_data_raw = _parse_waste_data_raw(waste_data_raw_temp)
        return waste_data_raw
    except (ValueError, KeyError, TypeError) as err:
        # ValueError can happen on datetime parsing if upstream format changes
        _LOGGER.error("Irado invalid and/or no data received from %s", url)
        raise ValueError(f"Invalid and/or no data received from {url}") from err
