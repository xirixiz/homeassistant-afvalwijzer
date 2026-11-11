"""Afvalwijzer circulus."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
import re
from typing import Any

import requests

from ..common.main_functions import waste_type_rename
from ..const.const import SENSOR_COLLECTORS_CIRCULUS

_LOGGER = logging.getLogger(__name__)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)


def _build_url(provider: str) -> str:
    url = SENSOR_COLLECTORS_CIRCULUS.get(provider)
    if not url:
        raise ValueError(f"Invalid provider: {provider}, please verify")
    return url


def _get_session_cookie(
    session: requests.Session,
    url: str,
    postal_code: str,
    house_number: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> tuple[dict[str, Any] | None, requests.cookies.RequestsCookieJar | None]:
    """Obtain a logged-in session cookie.

    Perform the zipcode registration call and return the response payload and
    authenticated cookie jar when successful.
    """
    raw_response = session.get(url, timeout=timeout, verify=verify)
    raw_response.raise_for_status()

    cookies = raw_response.cookies
    session_cookie = cookies.get("CB_SESSION", "")

    if not session_cookie:
        _LOGGER.error("Circulus: Unable to get Session Cookie (CB_SESSION missing)")
        return None, None

    match = re.search(r"__AT=(.*)&___TS=", session_cookie)
    authenticity_token = match.group(1) if match else ""

    data = {
        "authenticityToken": authenticity_token,
        "zipCode": postal_code,
        "number": house_number,
    }

    raw_response = session.post(
        f"{url}/register/zipcode.json",
        data=data,
        timeout=timeout,
        verify=verify,
    )
    raw_response.raise_for_status()

    return raw_response.json(), raw_response.cookies


def _address_suffix(address: str, house_number: str) -> str | None:
    """Return the suffix of an address line like "Kerklaan 3 c, 7311AA Apeldoorn".

    Return "" for the bare house number and None when the number doesn't match.
    """
    match = re.search(rf" {re.escape(str(house_number))}(?: ([^,]+))?,", address)
    if not match:
        return None
    return (match.group(1) or "").strip()


def _maybe_select_address(
    response: dict[str, Any],
    house_number: str,
    suffix: str,
) -> str:
    """Select an address when multiple options are returned.

    A postal code can cover several streets, so the list can hold other
    addresses with the same house number. Prefer the one whose suffix matches
    the configured suffix (case-insensitively), or the bare house number when
    no suffix is configured. Return its authentication URL, or an empty string
    when no address matches.
    """
    addresses = (response.get("customData") or {}).get("addresses") or []
    if not addresses:
        return ""

    for address in addresses:
        found = _address_suffix(address.get("address") or "", house_number)
        if found is not None and found.lower() == suffix.lower():
            return address.get("authenticationUrl") or ""

    if suffix:
        return ""

    _LOGGER.warning(
        "Circulus: %d addresses found for this postal code and house number, none "
        "without a suffix; using the first. Configure a suffix to choose another.",
        len(addresses),
    )
    return addresses[0].get("authenticationUrl") or ""


def _ensure_authenticated_address(
    session: requests.Session,
    url: str,
    response: dict[str, Any],
    *,
    house_number: str,
    suffix: str,
    timeout: tuple[float, float],
    verify: bool,
) -> bool:
    """Authenticate a specific address when required.

    Return False when Circulus offered several addresses and none matched.
    """
    if not (response.get("customData") or {}).get("addresses"):
        return True

    authentication_url = _maybe_select_address(response, house_number, suffix)
    if not authentication_url:
        return False

    # Rely on the session cookie jar: this call refreshes CB_SESSION, and passing
    # older cookies explicitly would override it on later requests.
    session.get(
        url + authentication_url,
        timeout=timeout,
        verify=verify,
    ).raise_for_status()
    return True


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    url: str,
    *,
    days_back: int = 14,
    days_forward: int = 90,
    timeout: tuple[float, float],
    verify: bool,
) -> list[dict[str, Any]]:
    """Fetch the raw garbage list from the API response."""
    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    end_date = (datetime.now() + timedelta(days=days_forward)).strftime("%Y-%m-%d")

    response = session.get(
        f"{url}/afvalkalender.json?from={start_date}&till={end_date}",
        headers={"Content-Type": "application/json"},
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()

    data = response.json()
    garbage = (data.get("customData") or {}).get("response", {}).get("garbage", [])

    return garbage or []


def _parse_waste_data_raw(
    waste_data_raw_temp: list[dict[str, Any]],
    postal_code: str = "",
) -> list[dict[str, str]]:
    waste_data_raw: list[dict[str, str]] = []

    for item in waste_data_raw_temp:
        waste_type = waste_type_rename(
            (item.get("code") or "").strip().lower(), postal_code
        )
        if not waste_type:
            continue

        for date in item.get("dates") or []:
            if not date:
                continue
            waste_data_raw.append({"type": waste_type, "date": date})

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
    suffix = (suffix or "").strip().upper()
    url = _build_url(provider)

    try:
        response, logged_in_cookies = _get_session_cookie(
            session,
            url,
            postal_code,
            house_number,
            timeout=timeout,
            verify=verify,
        )

        if not response or not logged_in_cookies:
            _LOGGER.error("Circulus: No waste data found (login/session failed)")
            return []

        if response.get("success") is False:
            # e.g. "Het opgegeven adres is niet bij ons bekend."
            _LOGGER.error(
                "Circulus did not accept the address: %s",
                response.get("flashMessage") or "no reason given",
            )
            return []

        if not _ensure_authenticated_address(
            session,
            url,
            response,
            house_number=house_number,
            suffix=suffix,
            timeout=timeout,
            verify=verify,
        ):
            _LOGGER.error(
                "Circulus: no address with suffix '%s' among the %d addresses found",
                suffix,
                len((response.get("customData") or {}).get("addresses") or []),
            )
            return []

        waste_data_raw_temp = _fetch_waste_data_raw_temp(
            session,
            url,
            timeout=timeout,
            verify=verify,
        )

        if not waste_data_raw_temp:
            _LOGGER.error("Circulus: No Waste data found for the selected address!")
            return []

        return _parse_waste_data_raw(waste_data_raw_temp, postal_code)

    except requests.exceptions.RequestException as err:
        _LOGGER.error("Circulus request error: %s", err)
        raise ValueError(err) from err
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("Circulus: Invalid and/or no data received from %s", url)
        raise ValueError(f"Invalid and/or no data received from {url}") from err
