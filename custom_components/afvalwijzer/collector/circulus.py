from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any, Dict, List, Optional, Tuple

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..const.const import _LOGGER, SENSOR_COLLECTORS_CIRCULUS
from ..common.main_functions import waste_type_rename


requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: Tuple[float, float] = (5.0, 60.0)


def _build_url(provider: str) -> str:
    url = SENSOR_COLLECTORS_CIRCULUS.get(provider)
    if not url:
        raise ValueError(f"Invalid provider: {provider}, please verify")
    return url


def _get_session_cookie(
    session: requests.Session,
    url: str,
    postal_code: str,
    street_number: str,
    *,
    timeout: Tuple[float, float],
    verify: bool,
) -> Tuple[Optional[Dict[str, Any]], Optional[requests.cookies.RequestsCookieJar]]:
    """
    Returns:
      - response (json dict) from /register/zipcode.json (or None)
      - logged_in_cookies (cookie jar) (or None)
    """
    raw_response = session.get(url, timeout=timeout, verify=verify)
    raw_response.raise_for_status()

    cookies = raw_response.cookies
    session_cookie = cookies.get("CB_SESSION", "")

    if not session_cookie:
        _LOGGER.error("Circulus: Unable to get Session Cookie (CB_SESSION missing)")
        return None, None

    # Extract authenticityToken from CB_SESSION: __AT=<token>&___TS=...
    match = re.search(r"__AT=(.*)&___TS=", session_cookie)
    authenticity_token = match.group(1) if match else ""

    data = {
        "authenticityToken": authenticity_token,
        "zipCode": postal_code,
        "number": street_number,
    }

    raw_response = session.post(
        f"{url}/register/zipcode.json",
        data=data,
        cookies=cookies,
        timeout=timeout,
        verify=verify,
    )
    raw_response.raise_for_status()

    response = raw_response.json()
    logged_in_cookies = raw_response.cookies
    return response, logged_in_cookies


def _maybe_select_address(
    response: Dict[str, Any],
    street_number: str,
    suffix: str,
) -> str:
    """
    Some responses require picking an address via authenticationUrl.
    Returns '' if none selected.
    """
    addresses = (response.get("customData") or {}).get("addresses") or []
    if not addresses:
        return ""

    # Keep original intent: if suffix given try to match address containing " <number> <suffix>"
    if suffix:
        search_pattern = rf" {re.escape(str(street_number))} {re.escape(suffix.lower())}\b"
        for address in addresses:
            address_str = (address.get("address") or "")
            if re.search(search_pattern, address_str):
                return address.get("authenticationUrl") or ""
        return ""
    else:
        return addresses[0].get("authenticationUrl") or ""


def _ensure_authenticated_address(
    session: requests.Session,
    url: str,
    response: Dict[str, Any],
    logged_in_cookies: requests.cookies.RequestsCookieJar,
    street_number: str,
    suffix: str,
    *,
    timeout: Tuple[float, float],
    verify: bool,
) -> None:
    """
    If the API indicates multiple/ambiguous addresses, select an address.
    This mirrors the original behavior: do a GET to authenticationUrl when present.
    """
    flash_message = response.get("flashMessage")
    if not flash_message:
        return

    authentication_url = _maybe_select_address(response, street_number, suffix)
    if not authentication_url:
        return

    session.get(
        url + authentication_url,
        cookies=logged_in_cookies,
        timeout=timeout,
        verify=verify,
    ).raise_for_status()


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    url: str,
    logged_in_cookies: requests.cookies.RequestsCookieJar,
    *,
    days_back: int = 14,
    days_forward: int = 90,
    timeout: Tuple[float, float],
    verify: bool,
) -> List[Dict[str, Any]]:
    """
    Returns the raw 'garbage' list from the response.
    """
    start_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
    end_date = (datetime.now() + timedelta(days=days_forward)).strftime("%Y-%m-%d")

    response = session.get(
        f"{url}/afvalkalender.json?from={start_date}&till={end_date}",
        headers={"Content-Type": "application/json"},
        cookies=logged_in_cookies,
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()
    data = response.json()

    garbage = (
        (data.get("customData") or {})
        .get("response", {})
        .get("garbage", [])
    )

    return garbage or []


def _parse_waste_data_raw(waste_data_raw_temp: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    waste_data_raw: List[Dict[str, str]] = []

    for item in waste_data_raw_temp:
        # Original: type derived from item["code"]
        waste_type = waste_type_rename((item.get("code") or "").strip().lower())
        if not waste_type:
            continue

        for date in item.get("dates") or []:
            if not date:
                continue
            # Original: date already in yyyy-mm-dd
            waste_data_raw.append({"type": waste_type, "date": date})

    return waste_data_raw


def get_waste_data_raw(
    provider: str,
    postal_code: str,
    street_number: str,
    suffix: str,
    *,
    session: Optional[requests.Session] = None,
    timeout: Tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
) -> List[Dict[str, str]]:
    """
    Collector-style function:
    - Always returns `waste_data_raw` (list)
    - Naming aligned: url -> waste_data_raw_temp -> waste_data_raw
    - Clear flow: cookie/session -> optional address selection -> fetch -> parse
    """
    session = session or requests.Session()
    suffix = (suffix or "").strip().upper()
    url = _build_url(provider)

    try:
        response, logged_in_cookies = _get_session_cookie(
            session,
            url,
            postal_code,
            street_number,
            timeout=timeout,
            verify=verify,
        )

        if not response or not logged_in_cookies:
            _LOGGER.error("Circulus: No waste data found (login/session failed)")
            return []

        _ensure_authenticated_address(
            session,
            url,
            response,
            logged_in_cookies,
            street_number,
            suffix,
            timeout=timeout,
            verify=verify,
        )

        waste_data_raw_temp = _fetch_waste_data_raw_temp(
            session,
            url,
            logged_in_cookies,
            timeout=timeout,
            verify=verify,
        )

        if not waste_data_raw_temp:
            _LOGGER.error("Circulus: No Waste data found!")
            return []

        waste_data_raw = _parse_waste_data_raw(waste_data_raw_temp)
        return waste_data_raw

    except requests.exceptions.RequestException as err:
        _LOGGER.error("Circulus request error: %s", err)
        raise ValueError(err) from err
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("Circulus: Invalid and/or no data received from %s", url)
        raise ValueError(f"Invalid and/or no data received from {url}") from err
