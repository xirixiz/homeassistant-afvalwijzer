"""Afvalwijzer rd4."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any

import requests

from ..common.main_functions import format_postal_code, waste_type_rename
from ..const.const import SENSOR_COLLECTORS_RD4

_LOGGER = logging.getLogger(__name__)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)


def _build_url(
    provider: str, postal_code: str, house_number: str, suffix: str, year: int
) -> str:
    if provider not in SENSOR_COLLECTORS_RD4:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    corrected_postal_code = format_postal_code(postal_code)

    return SENSOR_COLLECTORS_RD4[provider].format(
        corrected_postal_code,
        house_number,
        suffix,
        year,
    )


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    url: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> list[dict[str, Any]]:
    response = session.get(url, timeout=timeout, verify=verify)
    response.raise_for_status()
    data = response.json() or {}

    if not data:
        return []

    if not data.get("success"):
        # Keep original behavior: treat as address-not-found
        return []

    # Original: response["data"]["items"][0] is expected to be an iterable of entries
    items = (((data.get("data") or {}).get("items") or [])[:1] or [None])[0]
    return items or []


def _parse_waste_data_raw(
    waste_data_raw_temp: list[dict[str, Any]],
    postal_code: str = "",
) -> list[dict[str, str]]:
    waste_data_raw: list[dict[str, str]] = []

    for item in waste_data_raw_temp:
        date_str = item.get("date")
        if not date_str:
            continue

        waste_type = waste_type_rename(
            (item.get("type") or "").strip().lower(), postal_code
        )
        if not waste_type:
            continue

        waste_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
        waste_data_raw.append({"type": waste_type, "date": waste_date})

    return waste_data_raw


def get_waste_data_raw(
    provider: str,
    postal_code: str,
    house_number: str,
    suffix: str,
    *,
    session: requests.Session | None = None,
    timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = True,
) -> list[dict[str, str]]:
    """Return waste_data_raw."""

    session = session or requests.Session()
    current_year = datetime.now().year
    url = _build_url(provider, postal_code, house_number, suffix, current_year)

    try:
        waste_data_raw_temp = _fetch_waste_data_raw_temp(
            session,
            url,
            timeout=timeout,
            verify=verify,
        )

        # Also fetch next year, so the schedule does not run dry at the end of the
        # year. Next year's calendar may not be published yet, so failures are ignored.
        next_url = _build_url(
            provider, postal_code, house_number, suffix, current_year + 1
        )
        try:
            waste_data_raw_temp = waste_data_raw_temp + _fetch_waste_data_raw_temp(
                session,
                next_url,
                timeout=timeout,
                verify=verify,
            )
        except (requests.exceptions.RequestException, ValueError, TypeError) as err:
            _LOGGER.debug("RD4: no data for %s: %s", current_year + 1, err)

        if not waste_data_raw_temp:
            # Match original semantics: log based on likely cause
            # (If response empty or success false, caller expects [])
            _LOGGER.error("No waste data found or address not found!")
            return []

        waste_data_raw = _parse_waste_data_raw(waste_data_raw_temp, postal_code)
        return waste_data_raw

    except requests.exceptions.RequestException as err:
        _LOGGER.error("RD4 request error: %s", err)
        raise ValueError(err) from err
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("RD4: Invalid and/or no data received from %s", url)
        raise ValueError(f"Invalid and/or no data received from {url}") from err
