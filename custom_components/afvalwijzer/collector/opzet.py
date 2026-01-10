from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Tuple

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..common.main_functions import waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_OPZET

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: Tuple[float, float] = (5.0, 60.0)


def _build_base_url(provider: str) -> str:
    if provider not in SENSOR_COLLECTORS_OPZET:
        raise ValueError(f"Invalid provider: {provider}, please verify")
    return SENSOR_COLLECTORS_OPZET[provider]


def _fetch_address_list(
    session: requests.Session,
    base_url: str,
    postal_code: str,
    street_number: str,
    *,
    timeout: Tuple[float, float],
    verify: bool,
) -> List[Dict[str, Any]]:
    url_address = f"{base_url}/rest/adressen/{postal_code}-{street_number}"
    response = session.get(url_address, timeout=timeout, verify=verify)
    response.raise_for_status()
    data = response.json()
    return data or []


def _select_bag_id(
    response_address: List[Dict[str, Any]],
    suffix: str,
) -> str | None:
    if not response_address:
        return None

    # Original behavior: if multiple and suffix, match huisletter or huisnummerToevoeging
    if len(response_address) > 1 and suffix:
        for item in response_address:
            if (
                item.get("huisletter") == suffix
                or item.get("huisnummerToevoeging") == suffix
            ):
                return item.get("bagId")
        return None

    return response_address[0].get("bagId")


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    base_url: str,
    bag_id: str,
    *,
    timeout: Tuple[float, float],
    verify: bool,
) -> List[Dict[str, Any]]:
    url_waste = f"{base_url}/rest/adressen/{bag_id}/afvalstromen"
    response = session.get(url_waste, timeout=timeout, verify=verify)
    response.raise_for_status()
    data = response.json()
    return data or []


def _parse_waste_data_raw(
    waste_data_raw_temp: List[Dict[str, Any]],
) -> List[Dict[str, str]]:
    waste_data_raw: List[Dict[str, str]] = []

    for item in waste_data_raw_temp:
        date_str = item.get("ophaaldatum")
        if not date_str:
            continue

        waste_type = waste_type_rename((item.get("menu_title") or "").strip().lower())
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
    timeout: Tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
) -> List[Dict[str, str]]:
    """Collector-style function:
    - Always returns `waste_data_raw`
    - Naming aligned: response_address / waste_data_raw_temp / waste_data_raw
    - Keeps original selection logic for bagId
    """
    session = session or requests.Session()
    suffix = (suffix or "").strip().upper()

    base_url = _build_base_url(provider)

    # Preserve original intent: provider != "suez" computed, but original code never used it.
    # Keep it as a local in case you later want provider-specific verify behavior.
    _verify = provider != "suez"  # noqa: F841

    try:
        response_address = _fetch_address_list(
            session,
            base_url,
            postal_code,
            street_number,
            timeout=timeout,
            verify=verify,
        )

        if not response_address:
            _LOGGER.error("No waste data found!")
            return []

        bag_id = _select_bag_id(response_address, suffix)
        if not bag_id:
            _LOGGER.warning("Address not found!")
            return []

        waste_data_raw_temp = _fetch_waste_data_raw_temp(
            session,
            base_url,
            bag_id,
            timeout=timeout,
            verify=verify,
        )

        waste_data_raw = _parse_waste_data_raw(waste_data_raw_temp)
        return waste_data_raw

    except requests.exceptions.RequestException as err:
        _LOGGER.error("OPZET request error: %s", err)
        raise ValueError(err) from err
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("OPZET: Invalid and/or no data received from %s", base_url)
        raise ValueError(f"Invalid and/or no data received from {base_url}") from err
