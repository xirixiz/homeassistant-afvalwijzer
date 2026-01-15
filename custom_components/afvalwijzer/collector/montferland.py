"""Afvalwijzer integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..common.main_functions import format_postal_code, waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_MONTFERLAND

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)

_QUERY_START = "?Username=GSD&Password=gsd$2014"


def _build_url(provider: str) -> str:
    """Build the base URL for the Montferland collector."""
    url = SENSOR_COLLECTORS_MONTFERLAND.get(provider)
    if not url:
        raise ValueError(f"Invalid provider: {provider}, please verify")
    return url.rstrip("/")


def _fetch_address_data(
    session: requests.Session,
    base_url: str,
    postal_code: str,
    street_number: str,
    suffix: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> list[dict[str, Any]]:
    response = session.get(
        f"{base_url}/Login.ashx{_QUERY_START}",
        params={
            "Postcode": postal_code,
            "Huisnummer": street_number,
            "Toevoeging": suffix or "",
        },
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()
    return response.json() or []


def _extract_ids(address_data: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    """Extract administratie and adres identifiers."""
    if not address_data:
        return None, None

    first = address_data[0] or {}
    adres_id = first.get("AdresID")
    administratie_id = first.get("AdministratieID")

    return (
        str(administratie_id) if administratie_id else None,
        str(adres_id) if adres_id else None,
    )


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    base_url: str,
    administratie_id: str,
    adres_id: str,
    year: int,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> list[dict[str, Any]]:
    response = session.get(
        f"{base_url}/OphaalDatums.ashx/{_QUERY_START}",
        params={
            "ADM_ID": administratie_id,
            "ADR_ID": adres_id,
            "Jaar": str(year),
        },
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()
    return response.json() or []


def _parse_waste_data_raw(
    waste_data_raw_temp: list[dict[str, Any]],
) -> list[dict[str, str]]:
    waste_data_raw: list[dict[str, str]] = []

    for item in waste_data_raw_temp:
        date_str = item.get("Datum")
        if not date_str:
            continue

        soort = item.get("Soort")
        if not soort:
            continue

        waste_type = waste_type_rename(soort)
        if not waste_type:
            continue

        waste_date = datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S").strftime(
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
    timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
) -> list[dict[str, str]]:
    """Return waste_data_raw."""
    session = session or requests.Session()
    suffix = (suffix or "").strip()
    postal_code = format_postal_code(postal_code)

    try:
        base_url = _build_url(provider)

        address_data = _fetch_address_data(
            session,
            base_url,
            postal_code,
            str(street_number),
            suffix,
            timeout=timeout,
            verify=verify,
        )

        administratie_id, adres_id = _extract_ids(address_data)

        if not adres_id:
            _LOGGER.error("MONTFERLAND: AdresID not found!")
            return []
        if not administratie_id:
            _LOGGER.error("MONTFERLAND: AdministratieID not found!")
            return []

        year = datetime.today().year

        waste_data_raw_temp = _fetch_waste_data_raw_temp(
            session,
            base_url,
            administratie_id,
            adres_id,
            year,
            timeout=timeout,
            verify=verify,
        )

        if not waste_data_raw_temp:
            _LOGGER.error("No Waste data found!")
            return []

        return _parse_waste_data_raw(waste_data_raw_temp)

    except requests.exceptions.RequestException as err:
        _LOGGER.error("MONTFERLAND request error: %s", err)
        raise ValueError(err) from err
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("MONTFERLAND: Invalid and/or no data received")
        raise ValueError("Invalid and/or no data received from MONTFERLAND") from err
