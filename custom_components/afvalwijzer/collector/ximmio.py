from __future__ import annotations

from datetime import datetime, timedelta
import socket
from typing import Any, Dict, List, Tuple

import requests
from urllib3.exceptions import InsecureRequestWarning
from urllib3.util import connection as urllib3_connection

from ..common.main_functions import waste_type_rename
from ..const.const import (
    _LOGGER,
    SENSOR_COLLECTORS_XIMMIO,
    SENSOR_COLLECTORS_XIMMIO_IDS,
)

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: Tuple[float, float] = (5.0, 60.0)


def _post_ipv4_then_ipv6(
    session: requests.Session,
    url: str,
    **kwargs: Any,
) -> requests.Response:
    """Try POST via IPv4 first; if that fails (DNS/connect), try IPv6."""
    original_allowed = urllib3_connection.allowed_gai_family
    last_err: BaseException | None = None

    try:
        urllib3_connection.allowed_gai_family = lambda: socket.AF_INET
        return session.post(url=url, **kwargs)
    except requests.exceptions.RequestException as e_v4:
        last_err = e_v4
    finally:
        urllib3_connection.allowed_gai_family = original_allowed

    try:
        urllib3_connection.allowed_gai_family = lambda: socket.AF_INET6
        return session.post(url=url, **kwargs)
    except requests.exceptions.RequestException as e_v6:
        raise ValueError(f"POST failed (IPv4 then IPv6): {last_err}") from e_v6
    finally:
        urllib3_connection.allowed_gai_family = original_allowed


def _build_url(provider: str) -> str:
    # Provider must be present in IDS for this collector
    if provider not in SENSOR_COLLECTORS_XIMMIO_IDS:
        raise ValueError(f"Invalid provider: {provider} for XIMMIO, please verify")

    # Provider may have an override base URL, else fallback to "ximmio"
    if provider in SENSOR_COLLECTORS_XIMMIO:
        url = SENSOR_COLLECTORS_XIMMIO[provider]
    else:
        url = SENSOR_COLLECTORS_XIMMIO.get("ximmio")

    if not url:
        raise ValueError(f"Invalid provider: {provider} for XIMMIO, please verify")

    return url


def _fetch_address_data(
    session: requests.Session,
    url: str,
    provider: str,
    postal_code: str,
    street_number: str,
    suffix: str,
    *,
    timeout: Tuple[float, float],
) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "postCode": postal_code,
        "houseNumber": street_number,
        "companyCode": SENSOR_COLLECTORS_XIMMIO_IDS[provider],
    }

    # Keep original key casing to avoid breaking providers that depend on it
    if suffix:
        data["HouseLetter"] = suffix

    response = _post_ipv4_then_ipv6(
        session,
        url=f"{url}/api/FetchAdress",
        timeout=timeout,
        data=data,
    )
    response.raise_for_status()
    return response.json() or {}


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    url: str,
    provider: str,
    unique_id: str,
    community: str,
    start_date: datetime,
    end_date: str,
    *,
    timeout: Tuple[float, float],
) -> Dict[str, Any]:
    data = {
        "companyCode": SENSOR_COLLECTORS_XIMMIO_IDS[provider],
        "startDate": start_date.date(),  # original behavior: a date object
        "endDate": end_date,  # original behavior: yyyy-mm-dd string
        "community": community,
        "uniqueAddressID": unique_id,
    }

    response = _post_ipv4_then_ipv6(
        session,
        url=f"{url}/api/GetCalendar",
        timeout=timeout,
        data=data,
    )
    response.raise_for_status()
    return response.json() or {}


def _parse_waste_data_raw(waste_data_raw_temp: Dict[str, Any]) -> List[Dict[str, str]]:
    waste_data_raw: List[Dict[str, str]] = []

    for item in waste_data_raw_temp.get("dataList") or []:
        pickup_dates = sorted(item.get("pickupDates") or [])
        if not pickup_dates:
            continue

        waste_type = waste_type_rename(
            (item.get("_pickupTypeText") or "").strip().lower()
        )
        if not waste_type:
            continue

        waste_date = datetime.strptime(pickup_dates[0], "%Y-%m-%dT%H:%M:%S").strftime(
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
    timeout: Tuple[float, float] = _DEFAULT_TIMEOUT,
) -> List[Dict[str, str]]:
    """Collector-style function:
    - Always returns `waste_data_raw` (list)
    - Naming aligned: response/address -> waste_data_raw_temp -> waste_data_raw
    - Keeps IPv4->IPv6 POST fallback behavior
    """
    session = session or requests.Session()
    suffix = (suffix or "").strip().upper()

    try:
        url = _build_url(provider)

        now = datetime.now()
        end_date = (now.date() + timedelta(days=365)).strftime("%Y-%m-%d")

        # 1) address lookup
        response_address = _fetch_address_data(
            session,
            url,
            provider,
            postal_code,
            street_number,
            suffix,
            timeout=timeout,
        )

        data_list = response_address.get("dataList") or []
        if not data_list:
            _LOGGER.error("Address not found!")
            return []

        unique_id = data_list[0].get("UniqueId")
        community = data_list[0].get("Community")

        if not unique_id:
            _LOGGER.error("Address response missing UniqueId/Community!")
            return []

        # 2) calendar lookup
        waste_data_raw_temp = _fetch_waste_data_raw_temp(
            session,
            url,
            provider,
            unique_id,
            community,
            now,
            end_date,
            timeout=timeout,
        )

        if not waste_data_raw_temp:
            _LOGGER.error("Could not retrieve trash schedule!")
            return []

        waste_data_raw = _parse_waste_data_raw(waste_data_raw_temp)
        return waste_data_raw

    except requests.exceptions.RequestException as err:
        _LOGGER.error("XIMMIO request error: %s", err)
        raise ValueError(err) from err
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("XIMMIO: Invalid and/or no data received")
        raise ValueError("Invalid and/or no data received from XIMMIO") from err
