"""Afvalwijzer integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..common.main_functions import waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_KLIKOGROEP

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)


def _build_url(provider: str, postal_code: str, street_number: str) -> str:
    if provider not in SENSOR_COLLECTORS_KLIKOGROEP:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    provider_config = SENSOR_COLLECTORS_KLIKOGROEP[provider]
    provider_id = provider_config["id"]
    provider_base_url = provider_config["url"]

    provider_path = (
        f"/MyKliko/wasteCalendarJSON/{provider_id}/{postal_code}/{street_number}"
    )
    return f"https://{provider_base_url}{provider_path}"


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    url: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> dict[str, Any]:
    response = session.get(
        url,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "homeassistant-afvalwijzer",
        },
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()
    return response.json()


def _parse_waste_data_raw(waste_data_raw_temp: dict[str, Any]) -> list[dict[str, str]]:
    waste_data_raw: list[dict[str, str]] = []

    calendar = waste_data_raw_temp.get("calendar") or {}
    for date_str, waste_types in calendar.items():
        if not date_str or not waste_types:
            continue

        waste_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")

        for waste_code in waste_types:
            waste_type = waste_type_rename((waste_code or "").strip().lower())
            if not waste_type:
                continue

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
    url = _build_url(provider, postal_code, street_number)

    try:
        waste_data_raw_temp = _fetch_waste_data_raw_temp(
            session,
            url,
            timeout=timeout,
            verify=verify,
        )
    except requests.exceptions.RequestException as err:
        _LOGGER.error("KlikoGroep request error: %s", err)
        raise ValueError(err) from err
    except ValueError as err:
        _LOGGER.error("KlikoGroep invalid JSON from %s", url)
        raise ValueError(f"Invalid and/or no data received from {url}") from err

    if not waste_data_raw_temp:
        _LOGGER.error("No waste data found!")
        return []

    try:
        waste_data_raw = _parse_waste_data_raw(waste_data_raw_temp)
        return waste_data_raw
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("KlikoGroep: Invalid and/or no data received from %s", url)
        raise ValueError(f"Invalid and/or no data received from {url}") from err
