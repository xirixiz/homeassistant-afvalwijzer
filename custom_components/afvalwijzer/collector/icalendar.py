"""Afvalwijzer integration."""

from __future__ import annotations

from datetime import datetime

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..common.main_functions import parse_ical_waste_data
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


def get_waste_data_raw(
    provider: str,
    postal_code: str,
    house_number: str,
    suffix: str,
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
        waste_data_raw = parse_ical_waste_data(waste_data_raw_temp, postal_code)
        return waste_data_raw
    except (ValueError, KeyError) as err:
        # ValueError can occur on datetime parsing if upstream format changes
        _LOGGER.error("iCalendar invalid and/or no data received from %s", url)
        raise ValueError(f"Invalid and/or no data received from {url}") from err
