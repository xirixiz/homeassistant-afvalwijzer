from __future__ import annotations

from datetime import datetime
import uuid
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..const.const import _LOGGER, SENSOR_COLLECTORS_OMRIN
from ..common.main_functions import waste_type_rename, format_postal_code


requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: Tuple[float, float] = (5.0, 30.0)


def _build_url(provider: str, postal_code: str, street_number: str, suffix: str) -> str:
    if provider not in SENSOR_COLLECTORS_OMRIN:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    corrected_postal_code = format_postal_code(postal_code)

    return SENSOR_COLLECTORS_OMRIN[provider].format(
        corrected_postal_code,
        street_number,
        suffix,
    )


def _login(
    session: requests.Session,
    url: str,
    postal_code: str,
    street_number: str,
    suffix: str,
    *,
    timeout: Tuple[float, float],
    verify: bool,
) -> str:
    payload = {
        "Email": None,
        "Password": None,
        "PostalCode": postal_code,
        "HouseNumber": int(street_number),
        "HouseNumberExtension": suffix,
        "DeviceId": str(uuid.uuid4()),
        "Platform": "HomeAssistant",
        "AppVersion": "4.0.3.273",
        "OsVersion": "HomeAssistant 2024.1",
    }

    response = session.post(
        f"{url}/api/auth/login",
        json=payload,
        headers={
            "User-Agent": "Omrin.Afvalapp.Client/1.0",
            "Accept": "application/json",
        },
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()

    data = response.json()

    if not (data.get("success") and data.get("data")):
        raise ValueError(f"Login failed: {data.get('errors', 'Unknown error')}")

    token = data["data"].get("accessToken")
    if not token:
        raise ValueError("Not logged in")

    return token


def _fetch_calendar(
    session: requests.Session,
    url: str,
    token: str,
    *,
    timeout: Tuple[float, float],
    verify: bool,
) -> Sequence[Dict[str, Any]]:
    query = """
    query FetchCalendar {
      fetchCalendar {
        id
        date
        description
        type
        containerType
        placingTime
        state
      }
    }
    """

    response = session.post(
        f"{url}/graphql",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "GraphQL.Client/6.1.0.0",
            "Authorization": f"Bearer {token}",
        },
        json={"query": query},
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()

    result = response.json()

    if result.get("errors"):
        error_messages = ", ".join(
            e.get("message", str(e)) for e in result["errors"]
        )
        raise ValueError(f"GraphQL error: {error_messages}")

    return (result.get("data") or {}).get("fetchCalendar") or []


def _parse_waste_data_raw(
    waste_data_raw_temp: Sequence[Dict[str, Any]],
) -> List[Dict[str, str]]:
    waste_data_raw: List[Dict[str, str]] = []

    for item in waste_data_raw_temp:
        if not item.get("date"):
            continue

        waste_type = waste_type_rename(
            (item.get("type") or "").strip().lower()
        )
        if not waste_type:
            continue

        waste_date = datetime.strptime(
            item["date"], "%Y-%m-%d"
        ).strftime("%Y-%m-%d")

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
    token: Optional[str] = None,
    session: Optional[requests.Session] = None,
    timeout: Tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
) -> List[Dict[str, str]]:
    """
    Collector-style function:
    - Logs in only if no token is provided
    """
    url = _build_url(provider, postal_code, street_number, suffix)
    session = session or requests.Session()

    try:
        if not token:
            _LOGGER.debug("Omrin: no token supplied, logging in")
            token = _login(
                session,
                url,
                postal_code,
                street_number,
                suffix,
                timeout=timeout,
                verify=verify,
            )
        else:
            _LOGGER.debug("Omrin: token supplied, skipping login")

        waste_data_raw_temp = _fetch_calendar(
            session,
            url,
            token,
            timeout=timeout,
            verify=verify,
        )

        waste_data_raw = _parse_waste_data_raw(waste_data_raw_temp)

        return waste_data_raw

    except requests.exceptions.RequestException as err:
        _LOGGER.error("Omrin request error: %s", err)
        raise ValueError(err) from err
