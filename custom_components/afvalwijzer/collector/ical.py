"""Afvalwijzer integration."""

from __future__ import annotations

from datetime import datetime

from ical.calendar_stream import IcsCalendarStream
from ical.exceptions import CalendarParseError
import requests
from urllib3.exceptions import InsecureRequestWarning

from ..common.main_functions import waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_ICAL

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)


def _build_url(
    provider: str, year: int, postal_code: str, street_number: str, suffix: str
) -> str:
    if provider not in SENSOR_COLLECTORS_ICAL:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    return SENSOR_COLLECTORS_ICAL[provider].format(
        year,
        postal_code,
        street_number,
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


def _parse_waste_data_raw(waste_data_raw_temp: str) -> list[dict[str, str]]:
    if not waste_data_raw_temp:
        return []

    waste_data_raw: list[dict[str, str]] = []

    try:
        calendar = IcsCalendarStream.calendar_from_ics(waste_data_raw_temp)
    except CalendarParseError:
        return []

    for event in calendar.timeline:
        if not event.summary or not event.start:
            continue

        waste_type_raw = event.summary.strip().lower()
        waste_type = waste_type_rename(waste_type_raw)

        if not waste_type:
            continue

        waste_date = event.start.strftime("%Y-%m-%d")

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
    session: requests.Session | None = None,
    timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
) -> list[dict[str, str]]:
    """Return waste_data_raw."""

    session = session or requests.Session()

    year = datetime.today().year
    url = _build_url(provider, year, postal_code, street_number, suffix)

    try:
        waste_data_raw_temp = _fetch_waste_data_raw(
            session,
            url,
            timeout=timeout,
            verify=verify,
        )

    except requests.exceptions.RequestException as err:
        _LOGGER.error("iCal request error: %s", err)
        raise ValueError(err) from err

    if not waste_data_raw_temp:
        _LOGGER.error("No waste data found!")
        return []

    try:
        waste_data_raw = _parse_waste_data_raw(waste_data_raw_temp)
        return waste_data_raw
    except (ValueError, KeyError) as err:
        # ValueError can occur on datetime parsing if upstream format changes
        _LOGGER.error("iCal invalid and/or no data received from %s", url)
        raise ValueError(f"Invalid and/or no data received from {url}") from err
