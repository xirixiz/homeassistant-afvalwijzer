"""Afvalwijzer integration."""

from __future__ import annotations

from datetime import datetime

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..common.main_functions import waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_ICALENDAR

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)


def _build_url(
    provider: str, year: int, postal_code: str, house_number: str, suffix: str
) -> str:
    if provider not in SENSOR_COLLECTORS_ICALENDAR:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    return SENSOR_COLLECTORS_ICALENDAR[provider].format(
        year,
        postal_code,
        house_number,
        suffix,
    )


def _fetch_waste_data_raw(
    session: requests.Session,
    url: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> str:
    response = session.get(url, timeout=timeout, verify=verify)
    response.raise_for_status()
    return response.text or ""


def _parse_waste_data_raw(
    waste_data_raw_temp: str,
    custom_mapping: dict[str, str] | None = None,
) -> list[dict[str, str]]:
    if not waste_data_raw_temp:
        return []

    waste_data_raw: list[dict[str, str]] = []

    lines = waste_data_raw_temp.splitlines()
    event = {}  # Temporary dict to hold event data

    for line in lines:
        # Only process lines containing a colon
        if ":" not in line:
            continue

        # Split the line into field and value parts
        parts = line.split(":", 1)
        if len(parts) < 2:
            continue

        # Clean up the field name and value
        field = parts[0].split(";")[0].strip()
        value = parts[1].strip()

        if field == "BEGIN" and value == "VEVENT":
            event = {}  # Initialize a new event
        elif field == "SUMMARY":
            event["type"] = waste_type_rename(value.lower(), custom_mapping)
        elif field == "DTSTART":
            if value.isdigit() and len(value) == 8:
                # Format date as YYYY-MM-DD
                event["date"] = f"{value[:4]}-{value[4:6]}-{value[6:8]}"
            else:
                _LOGGER.debug(f"Unsupported waste_date format: {value}")
        elif field == "END" and value == "VEVENT":
            if "date" in event and "type" in event:
                waste_data_raw.append(event)
            else:
                _LOGGER.debug(f"Incomplete event data encountered: {event}")
            event = {}  # Reset the event for the next one

    return waste_data_raw


def get_waste_data_raw(
    provider: str,
    postal_code: str,
    house_number: str,
    suffix: str,
    custom_mapping: dict[str, str] | None = None,
    *,
    session: requests.Session | None = None,
    timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
) -> list[dict[str, str]]:
    """Return waste_data_raw."""

    session = session or requests.Session()

    year = datetime.today().year
    url = _build_url(provider, year, postal_code, house_number, suffix)

    try:
        waste_data_raw_temp = _fetch_waste_data_raw(
            session,
            url,
            timeout=timeout,
            verify=verify,
        )

    except requests.exceptions.RequestException as err:
        _LOGGER.error("iCalendar request error: %s", err)
        raise ValueError(err) from err

    if not waste_data_raw_temp:
        _LOGGER.error("No waste data found!")
        return []

    try:
        waste_data_raw = _parse_waste_data_raw(waste_data_raw_temp, custom_mapping)
        return waste_data_raw
    except (ValueError, KeyError) as err:
        # ValueError can occur on datetime parsing if upstream format changes
        _LOGGER.error("iCalendar invalid and/or no data received from %s", url)
        raise ValueError(f"Invalid and/or no data received from {url}") from err
