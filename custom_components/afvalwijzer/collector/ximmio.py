"""Afvalwijzer integration."""

from __future__ import annotations

from datetime import datetime, timedelta
import socket
from typing import Any

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

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)


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
    except requests.exceptions.RequestException as err_v4:
        last_err = err_v4
    finally:
        urllib3_connection.allowed_gai_family = original_allowed

    try:
        urllib3_connection.allowed_gai_family = lambda: socket.AF_INET6
        return session.post(url=url, **kwargs)
    except requests.exceptions.RequestException as err_v6:
        raise ValueError(f"POST failed (IPv4 then IPv6): {last_err}") from err_v6
    finally:
        urllib3_connection.allowed_gai_family = original_allowed


def _build_url(provider: str) -> str:
    if provider not in SENSOR_COLLECTORS_XIMMIO_IDS:
        raise ValueError(
            f"Invalid provider: {provider} for XIMMIO, please verify",
        )

    url = SENSOR_COLLECTORS_XIMMIO.get(provider) or SENSOR_COLLECTORS_XIMMIO.get(
        "ximmio"
    )
    if not url:
        raise ValueError(
            f"Invalid provider: {provider} for XIMMIO, please verify",
        )

    return url


def _get_data_list(response: dict[str, Any]) -> list[Any]:
    """Return response list under either dataList or datalist, else empty list."""
    for key in ("dataList", "datalist"):
        value = response.get(key)
        if isinstance(value, list):
            return value
    return []


def _fetch_address_data(
    session: requests.Session,
    url: str,
    provider: str,
    postal_code: str,
    street_number: str,
    suffix: str,
    *,
    timeout: tuple[float, float],
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "postCode": postal_code,
        "houseNumber": street_number,
        "companyCode": SENSOR_COLLECTORS_XIMMIO_IDS[provider],
    }

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
    timeout: tuple[float, float],
) -> dict[str, Any]:
    start_date_str = start_date.strftime("%Y-%m-%d")

    data: dict[str, Any] = {
        "companyCode": SENSOR_COLLECTORS_XIMMIO_IDS[provider],
        "startDate": start_date_str,
        "endDate": end_date,
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


def _parse_ximmio_date(value: str) -> str | None:
    """Parse Ximmio pickup date strings into yyyy-mm-dd."""
    if not value:
        return None

    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    try:
        cleaned = value.replace("Z", "")
        return datetime.fromisoformat(cleaned).strftime("%Y-%m-%d")
    except ValueError:
        return None


def _parse_waste_data_raw(
    waste_data_raw_temp: dict[str, Any],
) -> list[dict[str, str]]:
    waste_data_raw: list[dict[str, str]] = []

    for item in _get_data_list(waste_data_raw_temp):
        if not isinstance(item, dict):
            continue

        pickup_dates = sorted(item.get("pickupDates") or [])
        if not pickup_dates:
            continue

        waste_type_text = (item.get("_pickupTypeText") or "").strip().lower()
        waste_type = waste_type_rename(waste_type_text)
        if not waste_type:
            continue

        waste_date = _parse_ximmio_date(pickup_dates[0])
        if not waste_date:
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
) -> list[dict[str, str]]:
    """Return waste_data_raw."""
    session = session or requests.Session()
    suffix = (suffix or "").strip().upper()

    try:
        url = _build_url(provider)

        now = datetime.now()
        end_date = (now.date() + timedelta(days=365)).strftime("%Y-%m-%d")

        response_address = _fetch_address_data(
            session,
            url,
            provider,
            postal_code,
            street_number,
            suffix,
            timeout=timeout,
        )

        data_list = _get_data_list(response_address)
        if not data_list:
            _LOGGER.error("Address not found!")
            return []

        first = data_list[0] if isinstance(data_list[0], dict) else {}
        unique_id = first.get("UniqueId")
        community = first.get("Community")

        if not unique_id:
            _LOGGER.error("Address response missing UniqueId and or Community!")
            return []

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

        return _parse_waste_data_raw(waste_data_raw_temp)

    except requests.exceptions.RequestException as err:
        _LOGGER.error("XIMMIO request error: %s", err)
        raise ValueError(err) from err
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("XIMMIO: Invalid and/or no data received: %s", err)
        raise ValueError("Invalid and/or no data received from XIMMIO") from err
