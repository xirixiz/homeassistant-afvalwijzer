"""Afvalwijzer integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..common.main_functions import format_postal_code, waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_REINIS

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)


def _build_base_url(provider: str) -> str:
    if provider not in SENSOR_COLLECTORS_REINIS:
        raise ValueError(f"Invalid provider: {provider}, please verify")
    return SENSOR_COLLECTORS_REINIS[provider]


def _fetch_address_data(
    session: requests.Session,
    base_url: str,
    corrected_postal_code: str,
    street_number: str,
    suffix: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> list[dict[str, Any]]:
    address_url = f"{base_url}/adressen/{corrected_postal_code}:{street_number}{suffix}"
    response = session.get(address_url, timeout=timeout, verify=verify)
    response.raise_for_status()
    data = response.json()
    return data or []


def _extract_bagid(address_data: list[dict[str, Any]]) -> str | None:
    if not address_data:
        return None
    return (address_data[0] or {}).get("bagid")


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    base_url: str,
    bagid: str,
    year: int,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch waste calendar and waste stream data.

    Return a tuple containing the calendar entries and the afvalstroom lookup data.
    """
    kalender_url = f"{base_url}/rest/adressen/{bagid}/kalender/{year}"
    afvalstromen_url = f"{base_url}/rest/adressen/{bagid}/afvalstromen"

    waste_response = session.get(kalender_url, timeout=timeout, verify=verify)
    waste_response.raise_for_status()

    afvalstroom_response = session.get(afvalstromen_url, timeout=timeout, verify=verify)
    afvalstroom_response.raise_for_status()

    return (waste_response.json() or []), (afvalstroom_response.json() or [])


def _parse_waste_data_raw(
    waste_data_raw_temp: list[dict[str, Any]],
    afvalstroom_response: list[dict[str, Any]],
) -> list[dict[str, str]]:
    # Build lookup dict once (faster and clearer than next(...) per item)
    afvalstroom_map: dict[Any, str] = {}
    for a in afvalstroom_response:
        afval_id = a.get("id")
        title = a.get("title")
        if afval_id is None or not title:
            continue
        afvalstroom_map[afval_id] = title

    waste_data_raw: list[dict[str, str]] = []

    for item in waste_data_raw_temp:
        ophalen = item.get("ophaaldatum")
        afvalstroom_id = item.get("afvalstroom_id")
        if not ophalen or afvalstroom_id is None:
            continue

        title = afvalstroom_map.get(afvalstroom_id)
        if not title:
            continue

        afval_type = waste_type_rename(title)
        if not afval_type:
            continue

        # Original code kept date as-is (already YYYY-MM-DD); keep that behavior.
        waste_data_raw.append({"type": afval_type, "date": ophalen})

    return waste_data_raw


def get_waste_data_raw(
    provider: str,
    postal_code: str,
    street_number: str,
    suffix: str = "",
    *,
    session: requests.Session | None = None,
    timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
) -> list[dict[str, str]]:
    """Return waste_data_raw."""

    session = session or requests.Session()
    base_url = _build_base_url(provider)

    try:
        corrected_postal_code = format_postal_code(postal_code)
        suffix = suffix or ""

        address_data = _fetch_address_data(
            session,
            base_url,
            corrected_postal_code,
            street_number,
            suffix,
            timeout=timeout,
            verify=verify,
        )

        bagid = _extract_bagid(address_data)
        if not bagid:
            _LOGGER.error("No address found, missing bagid!")
            return []

        year = datetime.now().year
        waste_data_raw_temp, afvalstroom_response = _fetch_waste_data_raw_temp(
            session,
            base_url,
            bagid,
            year,
            timeout=timeout,
            verify=verify,
        )

        waste_data_raw = _parse_waste_data_raw(
            waste_data_raw_temp, afvalstroom_response
        )
        return waste_data_raw

    except requests.exceptions.RequestException as err:
        _LOGGER.error("Reinis request error: %s", err)
        raise ValueError(err) from err
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("Reinis: Invalid and/or no data received from %s", base_url)
        raise ValueError(f"Invalid and/or no data received from {base_url}") from err
