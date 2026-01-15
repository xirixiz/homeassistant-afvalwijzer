"""Afvalwijzer integration."""

from __future__ import annotations

from datetime import datetime

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..common.main_functions import waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_DEAFVALAPP

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)


def _build_url(provider: str, postal_code: str, street_number: str, suffix: str) -> str:
    if provider not in SENSOR_COLLECTORS_DEAFVALAPP:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    return SENSOR_COLLECTORS_DEAFVALAPP[provider].format(
        postal_code,
        street_number,
        suffix,
    )


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    url: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> str:
    response = session.get(url, timeout=timeout, verify=verify)
    response.raise_for_status()
    # Keep original behavior: treat body as text (CSV-ish)
    return response.text or ""


def _parse_waste_data_raw(waste_data_raw_temp: str) -> list[dict[str, str]]:
    # Original behavior: if empty -> []
    if not waste_data_raw_temp:
        return []

    waste_data_raw: list[dict[str, str]] = []

    # Each row: "<type>;<date>;<date>;...;"
    for row in waste_data_raw_temp.strip().split("\n"):
        row = row.strip()
        if not row:
            continue

        parts = row.split(";")
        if not parts:
            continue

        waste_type_raw = parts[0].strip().lower()
        waste_type = waste_type_rename(waste_type_raw)

        # Keep safe behavior: if waste_type_rename returns empty/None, skip row
        if not waste_type:
            continue

        # Original code used [1:-1] to ignore trailing empty after last ';'
        for date_str in parts[1:-1]:
            date_str = date_str.strip()
            if not date_str:
                continue

            waste_date = datetime.strptime(date_str, "%d-%m-%Y").strftime("%Y-%m-%d")
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
    verify: bool = False,
) -> list[dict[str, str]]:
    """Return waste_data_raw."""

    session = session or requests.Session()
    url = _build_url(provider, postal_code, street_number, suffix)

    try:
        waste_data_raw_temp = _fetch_waste_data_raw_temp(
            session,
            url,
            timeout=timeout,
            verify=verify,
        )

    except requests.exceptions.RequestException as err:
        _LOGGER.error("DeAfvalApp request error: %s", err)
        raise ValueError(err) from err

    if not waste_data_raw_temp:
        _LOGGER.error("No waste data found!")
        return []

    try:
        waste_data_raw = _parse_waste_data_raw(waste_data_raw_temp)
        return waste_data_raw
    except (ValueError, KeyError) as err:
        # ValueError can occur on datetime parsing if upstream format changes
        _LOGGER.error("DeAfvalApp invalid and/or no data received from %s", url)
        raise ValueError(f"Invalid and/or no data received from {url}") from err
