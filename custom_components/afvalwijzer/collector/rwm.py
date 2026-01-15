"""Afvalwijzer integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..common.main_functions import waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_RWM

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)


def _fetch_address_data(
    session: requests.Session,
    postal_code: str,
    street_number: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> list[dict[str, Any]]:
    url = SENSOR_COLLECTORS_RWM["getAddress"].format(postal_code, street_number)
    response = session.get(url, timeout=timeout, verify=verify)
    response.raise_for_status()
    return response.json() or []


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    bag_id: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> list[dict[str, Any]]:
    url = SENSOR_COLLECTORS_RWM["getSchedule"].format(bag_id)
    response = session.get(url, timeout=timeout, verify=verify)
    response.raise_for_status()
    return response.json() or []


def _parse_waste_data_raw(
    waste_data_raw_temp: list[dict[str, Any]],
) -> list[dict[str, str]]:
    waste_data_raw: list[dict[str, str]] = []

    for item in waste_data_raw_temp:
        date_str = item.get("ophaaldatum")
        if not date_str:
            continue

        waste_type = waste_type_rename((item.get("title") or "").strip().lower())
        if not waste_type:
            continue

        waste_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
        waste_data_raw.append(
            {
                "type": waste_type,
                "date": waste_date,
            }
        )

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

    if provider != "rwm":
        raise ValueError(f"Invalid provider: {provider}, please verify")

    session = session or requests.Session()

    try:
        address_data = _fetch_address_data(
            session,
            postal_code,
            street_number,
            timeout=timeout,
            verify=verify,
        )

        if not address_data:
            _LOGGER.error("Address not found!")
            return []

        bag_id = address_data[0].get("bagid")
        if not bag_id:
            _LOGGER.error("Address found but bagid missing!")
            return []

        waste_data_raw_temp = _fetch_waste_data_raw_temp(
            session,
            bag_id,
            timeout=timeout,
            verify=verify,
        )

        if not waste_data_raw_temp:
            _LOGGER.error("Could not retrieve trash schedule!")
            return []

        waste_data_raw = _parse_waste_data_raw(waste_data_raw_temp)
        return waste_data_raw

    except requests.exceptions.RequestException as err:
        _LOGGER.error("RWM request error: %s", err)
        raise ValueError(err) from err
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("RWM: Invalid and/or no data received")
        raise ValueError("Invalid and/or no data received from RWM") from err
