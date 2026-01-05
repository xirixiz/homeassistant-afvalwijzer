from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..const.const import _LOGGER, SENSOR_COLLECTORS_IRADO
from ..common.main_functions import waste_type_rename, format_postal_code


requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: Tuple[float, float] = (5.0, 60.0)

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
    timeout: Tuple[float, float],
    verify: bool,
) -> Dict[str, Any]:
    raw_response = session.get(
        url,
        headers=_DEFAULT_HEADERS,
        timeout=timeout,
        verify=verify,
    )
    raw_response.raise_for_status()
    return raw_response.json()


def _parse_waste_data_raw(waste_data_raw_temp: Dict[str, Any]) -> List[Dict[str, str]]:
    if not waste_data_raw_temp:
        return []

    # Preserve original behavior: if invalid -> []
    if not waste_data_raw_temp.get("valid", False):
        return []

    pickups = (
        waste_data_raw_temp.get("calendar_data", {})
        .get("pickups", {})
    )

    waste_data_raw: List[Dict[str, str]] = []

    # Structure: {year: {month: {day: [ {date,type,...}, ... ]}}}
    for _year, months in pickups.items():
        if not isinstance(months, dict):
            continue

        for _month, days in months.items():
            if not isinstance(days, dict):
                continue

            for _day, items in days.items():
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

                    waste_date = datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
                    waste_data_raw.append({"type": waste_type, "date": waste_date})

    return waste_data_raw


def get_waste_data_raw(
    provider: str,
    postal_code: str,
    street_number: str,
    suffix: str,
    *,
    session: Optional[requests.Session] = None,
    timeout: Tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
) -> List[Dict[str, str]]:
    """
    Collector-style function:
    - Always returns `waste_data_raw`
    - Naming: url -> waste_data_raw_temp -> waste_data_raw
    - Same behavior as original, with safer parsing and clearer structure
    """
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
