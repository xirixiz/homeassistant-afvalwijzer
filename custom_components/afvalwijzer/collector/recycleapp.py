"""Afvalwijzer recycleapp."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Any

import requests

from ..common.main_functions import format_postal_code, waste_type_rename
from ..const.const import SENSOR_COLLECTORS_RECYCLEAPP

_LOGGER = logging.getLogger(__name__)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)

_X_CONSUMER = "recycleapp.be"


def _build_url(provider: str) -> str:
    """Build the base URL for the RecycleApp collector."""
    url = SENSOR_COLLECTORS_RECYCLEAPP.get(provider)

    if not url:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    return url.rstrip("/") + "/"


def _build_headers() -> dict[str, str]:
    """Build RecycleCMS headers."""
    return {
        "x-consumer": _X_CONSUMER,
        "User-Agent": "",
        "Accept": "application/json",
    }


def _fetch_postcode_ids(
    session: requests.Session,
    base_url: str,
    postal_code: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> list[str]:
    """Fetch postcode ids (a query can match more than one zipcode entry)."""
    response = session.get(
        f"{base_url}zipcodes",
        params={"q": postal_code},
        headers=_build_headers(),
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()

    data = response.json() or {}
    items = data.get("items") or []

    postcode_ids = [str(item["id"]) for item in items if item.get("id")]

    if not postcode_ids:
        raise ValueError("RecycleApp: postcode_id not found")

    return postcode_ids


def _fetch_street_id(
    session: requests.Session,
    base_url: str,
    street_name: str,
    postcode_id: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> str | None:
    """Fetch street id for a single postcode id, or None if not found there."""
    response = session.get(
        f"{base_url}streets",
        params={
            "q": street_name,
            "zipcodes": postcode_id,
        },
        headers=_build_headers(),
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()

    data = response.json() or {}
    items = data.get("items") or []

    if not items:
        return None

    for item in items:
        if item.get("name") == street_name and item.get("id"):
            return str(item["id"])

    if items[0].get("id"):
        return str(items[0]["id"])

    return None


def _fetch_postcode_and_street_id(
    session: requests.Session,
    base_url: str,
    postal_code: str,
    street_name: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> tuple[str, str]:
    """Fetch the postcode id and street id, trying every matching zipcode.

    RecycleApp's zipcode lookup can return more than one entry for a query
    (e.g. shared postal codes across municipalities). The street must be
    looked up per zipcode id, so try each one until a street is found.
    """
    postcode_ids = _fetch_postcode_ids(
        session,
        base_url,
        postal_code,
        timeout=timeout,
        verify=verify,
    )

    for postcode_id in postcode_ids:
        street_id = _fetch_street_id(
            session,
            base_url,
            street_name,
            postcode_id,
            timeout=timeout,
            verify=verify,
        )

        if street_id:
            return postcode_id, street_id

    raise ValueError("RecycleApp: street_id not found")


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    base_url: str,
    postcode_id: str,
    street_id: str,
    house_number: str,
    *,
    days_forward: int = 60,
    timeout: tuple[float, float],
    verify: bool,
) -> dict[str, Any]:
    """Fetch raw collection data."""
    startdate = datetime.now().strftime("%Y-%m-%d")
    enddate = (datetime.now() + timedelta(days=days_forward)).strftime("%Y-%m-%d")

    response = session.get(
        f"{base_url}collections",
        params={
            "zipcodeId": postcode_id,
            "streetId": street_id,
            "houseNumber": house_number,
            "fromDate": startdate,
            "untilDate": enddate,
            "size": "100",
        },
        headers=_build_headers(),
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()

    return response.json() or {}


def _parse_waste_data_raw(
    waste_data_raw_temp: dict[str, Any],
    postal_code: str = "",
) -> list[dict[str, str]]:
    """Parse raw RecycleCMS response."""
    waste_data_raw: list[dict[str, str]] = []

    for item in waste_data_raw_temp.get("items") or []:
        timestamp = item.get("timestamp")

        if not timestamp:
            continue

        fraction = item.get("fraction") or {}
        name = fraction.get("name") or {}
        name_nl = name.get("nl")

        if not name_nl:
            continue

        exception = item.get("exception") or {}

        if exception.get("replacedBy"):
            continue

        waste_type = waste_type_rename(name_nl, postal_code)

        if not waste_type:
            continue

        waste_date = datetime.strptime(
            timestamp,
            "%Y-%m-%dT%H:%M:%S.000Z",
        ).strftime("%Y-%m-%d")

        waste_data_raw.append(
            {
                "type": waste_type,
                "date": waste_date,
            }
        )

    return sorted(
        waste_data_raw,
        key=lambda item: (item["date"], item["type"]),
    )


def get_waste_data_raw(
    provider: str,
    postal_code: str,
    house_number: str,
    suffix: str,
    street_name: str | None = None,
    *,
    access_token: str | None = None,
    session: requests.Session | None = None,
    timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = True,
) -> list[dict[str, str]]:
    """Return waste_data_raw."""
    del suffix
    del access_token

    session = session or requests.Session()

    try:
        base_url = _build_url(provider)
        postal_code = format_postal_code(postal_code)

        if not street_name:
            _LOGGER.error("RECYCLEAPP: street_name is required")
            return []

        postcode_id, street_id = _fetch_postcode_and_street_id(
            session,
            base_url,
            postal_code,
            street_name,
            timeout=timeout,
            verify=verify,
        )

        waste_data_raw_temp = _fetch_waste_data_raw_temp(
            session,
            base_url,
            postcode_id,
            street_id,
            str(house_number),
            timeout=timeout,
            verify=verify,
        )

        if not waste_data_raw_temp:
            _LOGGER.error("No Waste data found!")
            return []

        return _parse_waste_data_raw(
            waste_data_raw_temp,
            postal_code,
        )

    except requests.exceptions.RequestException as err:
        _LOGGER.error(
            "RECYCLEAPP request error: %s",
            err,
        )
        raise ValueError(err) from err

    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("RECYCLEAPP: Invalid and/or no data received")
        raise ValueError("Invalid and/or no data received from RECYCLEAPP") from err
