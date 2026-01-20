"""Afvalwijzer integration."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
import uuid

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..common.main_functions import format_postal_code, waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_OMRIN

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 30.0)


def _build_url(provider: str, postal_code: str, street_number: str, suffix: str) -> str:
    if provider not in SENSOR_COLLECTORS_OMRIN:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    corrected_postal_code = format_postal_code(postal_code)

    return SENSOR_COLLECTORS_OMRIN[provider].format(
        corrected_postal_code,
        street_number,
        suffix,
    )


def _normalize_token(token: str | None) -> str | None:
    """Allow passing either a raw token or 'Bearer <token>'."""
    if not token:
        return None
    token = token.strip()
    if not token:
        return None
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token or None


def _login(
    session: requests.Session,
    url: str,
    postal_code: str,
    street_number: str,
    suffix: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
    device_id: str | None = None,
) -> str:
    payload = {
        "Email": None,
        "Password": None,
        # keep original behavior: use raw input postal_code here
        "PostalCode": postal_code,
        "HouseNumber": int(street_number),
        "HouseNumberExtension": suffix,
        "DeviceId": device_id or str(uuid.uuid4()),
        "Platform": "Android",
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

    data = response.json() if response.content else {}
    if not (data.get("success") and data.get("data")):
        raise ValueError(f"Login failed: {data.get('errors', 'Unknown error')}")

    token = (data.get("data") or {}).get("accessToken")
    if not token:
        raise ValueError("Not logged in")

    return token


def _fetch_calendar(
    session: requests.Session,
    url: str,
    token: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> Sequence[dict[str, Any]]:
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

    result = response.json() if response.content else {}

    if result.get("errors"):
        error_messages = ", ".join(e.get("message", str(e)) for e in result["errors"])
        raise ValueError(f"GraphQL error: {error_messages}")

    return (result.get("data") or {}).get("fetchCalendar") or []


def _parse_waste_data_raw(
    waste_data_raw_temp: Sequence[dict[str, Any]],
) -> list[dict[str, str]]:
    waste_data_raw: list[dict[str, str]] = []

    for item in waste_data_raw_temp:
        date_str = item.get("date")
        if not date_str:
            continue

        waste_type = waste_type_rename((item.get("type") or "").strip().lower())
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
    token: str | None = None,
    session: requests.Session | None = None,
    timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
    device_id: str | None = None,
) -> list[dict[str, str]]:
    """Return waste_data_raw."""

    url = _build_url(provider, postal_code, street_number, suffix)
    session = session or requests.Session()

    try:
        token = _normalize_token(token)

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
                device_id=device_id,
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
