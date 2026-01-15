"""Afvalwijzer integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..common.main_functions import waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_ROVA

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)


def _build_url(provider: str, postal_code: str, street_number: str, suffix: str) -> str:
    base_url = SENSOR_COLLECTORS_ROVA.get(provider)
    if not base_url:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    suffix = (suffix or "").strip().upper()

    # Keep original behavior: take=10
    return (
        f"{base_url}/api/waste-calendar/upcoming"
        f"?houseNumber={street_number}&addition={suffix}&postalcode={postal_code}&take=10"
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
    data = response.json()
    return data or []


def _parse_waste_data_raw(
    waste_data_raw_temp: list[dict[str, Any]],
) -> list[dict[str, str]]:
    waste_data_raw: list[dict[str, str]] = []

    for item in waste_data_raw_temp:
        waste_title = ((item.get("wasteType") or {}).get("title")) or ""
        waste_type = waste_type_rename(waste_title)
        if not waste_type:
            continue

        date_str = item.get("date")
        if not date_str:
            continue

        # Input format: 2024-01-01T00:00:00Z
        waste_date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%SZ").strftime(
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
        _LOGGER.error("ROVA request error: %s", err)
        raise ValueError(err) from err
    except ValueError as err:
        _LOGGER.error("ROVA invalid JSON from %s", url)
        raise ValueError(f"Invalid and/or no data received from {url}") from err

    if not waste_data_raw_temp:
        _LOGGER.error("No waste data found!")
        return []

    try:
        waste_data_raw = _parse_waste_data_raw(waste_data_raw_temp)
        return waste_data_raw
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("ROVA: Invalid and/or no data received from %s", url)
        raise ValueError(f"Invalid and/or no data received from {url}") from err
