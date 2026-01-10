from __future__ import annotations

"""
Straatbeeld collector (STRAATBEELD) adapted to your project style.

- entrypoint: get_waste_data_raw(provider, postal_code, street_number, suffix)
- returns: waste_data_raw (list[{"type": <renamed_type>, "date": "YYYY-MM-DD"}])
- naming: waste_data_raw_temp -> waste_data_raw
"""

from datetime import datetime
from typing import Any, Dict, List, Tuple

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..common.main_functions import format_postal_code, waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_STRAATBEELD

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: Tuple[float, float] = (5.0, 60.0)


def _build_url(provider: str) -> str:
    """Expects:
    SENSOR_COLLECTORS_STRAATBEELD = {"straatbeeld": "https://drimmelen.api.straatbeeld.online"}
    """
    url = SENSOR_COLLECTORS_STRAATBEELD.get(provider)
    if not url:
        raise ValueError(f"Invalid provider: {provider}, please verify")
    return url.rstrip("/")


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    base_url: str,
    postal_code: str,
    street_number: str,
    suffix: str,
    *,
    timeout: Tuple[float, float],
    verify: bool,
) -> Dict[str, Any]:
    headers = {
        "accept": "application/json",
        "content-type": "application/json",
    }
    payload = {
        # Keep API field names as required by endpoint
        "postal_code": postal_code,
        "house_number": street_number,
        "house_letter": suffix or "",
    }

    response = session.post(
        f"{base_url}/v1/waste-calendar",
        headers=headers,
        json=payload,
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()
    return response.json() or {}


def _parse_waste_data_raw(waste_data_raw_temp: Dict[str, Any]) -> List[Dict[str, str]]:
    waste_data_raw: List[Dict[str, str]] = []

    collections = waste_data_raw_temp.get("collections") or {}
    for _, months in collections.items():
        if not isinstance(months, dict):
            continue

        for _, days in months.items():
            if not isinstance(days, list):
                continue

            for day in days:
                date_str = (
                    ((day.get("date") or {}).get("formatted"))
                    if isinstance(day, dict)
                    else None
                )
                if not date_str:
                    continue

                waste_date = datetime.strptime(date_str, "%Y-%m-%d").strftime(
                    "%Y-%m-%d"
                )

                for item in day.get("data") or []:
                    name = item.get("name")
                    if not name:
                        continue

                    waste_type = waste_type_rename(name)
                    if not waste_type:
                        continue

                    waste_data_raw.append({"type": waste_type, "date": waste_date})

    return sorted(waste_data_raw, key=lambda d: (d["date"], d["type"]))


def get_waste_data_raw(
    provider: str,
    postal_code: str,
    street_number: str,
    suffix: str,
    *,
    session: requests.Session | None = None,
    timeout: Tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
) -> List[Dict[str, str]]:
    """STRAATBEELD collector in your project style."""
    session = session or requests.Session()
    postal_code = format_postal_code(postal_code)
    suffix = (suffix or "").strip()

    try:
        base_url = _build_url(provider)

        waste_data_raw_temp = _fetch_waste_data_raw_temp(
            session,
            base_url,
            postal_code,
            str(street_number),
            suffix,
            timeout=timeout,
            verify=verify,
        )

        if not waste_data_raw_temp:
            _LOGGER.error("No Waste data found!")
            return []

        waste_data_raw = _parse_waste_data_raw(waste_data_raw_temp)
        return waste_data_raw

    except requests.exceptions.RequestException as err:
        _LOGGER.error("STRAATBEELD request error: %s", err)
        raise ValueError(err) from err
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("STRAATBEELD: Invalid and/or no data received")
        raise ValueError("Invalid and/or no data received from STRAATBEELD") from err
