"""Afvalwijzer integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..common.main_functions import waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_BURGERPORTAAL

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)

# Keep existing behavior: static API key in code (not ideal, but not changing functionality)
_API_KEY = "AIzaSyA6NkRqJypTfP-cjWzrZNFJzPUbBaGjOdk"

_BASE_GOOGLE_SIGNUP_URL = (
    "https://www.googleapis.com/identitytoolkit/v3/relyingparty/signupNewUser"
)
_BASE_GOOGLE_SECURETOKEN_URL = "https://securetoken.googleapis.com/v1/token"
_BASE_BURGERPORTAAL_URL = (
    "https://europe-west3-burgerportaal-production.cloudfunctions.net/exposed"
)


def _build_org_id(provider: str) -> str:
    if provider not in SENSOR_COLLECTORS_BURGERPORTAAL:
        raise ValueError(f"Invalid provider: {provider}, please verify")
    return SENSOR_COLLECTORS_BURGERPORTAAL[provider]


def _signup_anonymous(
    session: requests.Session,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> dict[str, Any]:
    response = session.post(
        f"{_BASE_GOOGLE_SIGNUP_URL}?key={_API_KEY}",
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()
    return response.json()


def _refresh_id_token(
    session: requests.Session,
    refresh_token: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> str:
    response = session.post(
        f"{_BASE_GOOGLE_SECURETOKEN_URL}?key={_API_KEY}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "refresh_token", "refresh_token": refresh_token},
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()

    data = response.json()
    id_token = data.get("id_token")
    if not id_token:
        raise KeyError("Missing id_token in securetoken response")
    return id_token


def _get_auth_token(
    session: requests.Session,
    *,
    timeout: tuple[float, float],
    verify: bool,
    id_token: str | None = None,
    refresh_token: str | None = None,
) -> tuple[str, str | None]:
    """Obtain an authentication token.

    Do not log in if a token is already present.
    - Reuse id_token if provided.
    - Refresh id_token using refresh_token if provided.
    - Otherwise create a new anonymous user and refresh to obtain tokens.

    Return a tuple of (id_token, refresh_token).
    """
    if id_token:
        return id_token, refresh_token

    if refresh_token:
        return _refresh_id_token(
            session, refresh_token, timeout=timeout, verify=verify
        ), refresh_token

    signup = _signup_anonymous(session, timeout=timeout, verify=verify)
    if not signup:
        raise ValueError("Unable to fetch id and refresh token")

    refresh_token = signup.get("refreshToken")
    if not refresh_token:
        raise KeyError("Missing refreshToken in signup response")

    id_token = _refresh_id_token(session, refresh_token, timeout=timeout, verify=verify)
    return id_token, refresh_token


def _fetch_address_list(
    session: requests.Session,
    org_id: str,
    postal_code: str,
    street_number: str,
    id_token: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> list[dict[str, Any]]:
    response = session.get(
        f"{_BASE_BURGERPORTAAL_URL}/organisations/{org_id}/address"
        f"?zipcode={postal_code}&housenumber={street_number}",
        headers={"authorization": id_token},
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()
    data = response.json()
    return data or []


def _select_address_id(
    address_list: list[dict[str, Any]],
    suffix: str,
) -> str | None:
    if not address_list:
        return None

    if suffix:
        for item in address_list:
            addition = item.get("addition")
            if addition and addition.casefold() == suffix.casefold():
                return item.get("addressId")
        return None

    return address_list[0].get("addressId")


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    org_id: str,
    address_id: str,
    id_token: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> list[dict[str, Any]]:
    response = session.get(
        f"{_BASE_BURGERPORTAAL_URL}/organisations/{org_id}/address/{address_id}/calendar",
        headers={"authorization": id_token},
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()
    data = response.json()
    return data or []


def _parse_waste_data_raw(
    waste_data_raw_temp: list[dict[str, Any]],
) -> list[dict[str, str]]:
    waste_data_raw: list[dict[str, str]] = []

    for item in waste_data_raw_temp:
        collection_dt = item.get("collectionDate")
        if not collection_dt:
            continue

        fraction = item.get("fraction")
        if not fraction:
            continue

        waste_type = waste_type_rename(fraction.strip().lower())
        if not waste_type:
            continue

        # Original behavior: take date part before "T"
        date_part = collection_dt.split("T", 1)[0]
        waste_date = datetime.strptime(date_part, "%Y-%m-%d").strftime("%Y-%m-%d")

        waste_data_raw.append({"type": waste_type, "date": waste_date})

    # Preserve original behavior: sorted by date
    return sorted(waste_data_raw, key=lambda d: d["date"])


def get_waste_data_raw(
    provider: str,
    postal_code: str,
    street_number: str,
    suffix: str,
    *,
    session: requests.Session | None = None,
    timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
    # Optional reuse to avoid re-login (requirement)
    id_token: str | None = None,
    refresh_token: str | None = None,
) -> list[dict[str, str]]:
    """Return waste_data_raw."""
    session = session or requests.Session()
    suffix = (suffix or "").strip().upper()
    org_id = _build_org_id(provider)

    try:
        id_token, refresh_token = _get_auth_token(
            session,
            timeout=timeout,
            verify=verify,
            id_token=id_token,
            refresh_token=refresh_token,
        )

        address_list = _fetch_address_list(
            session,
            org_id,
            postal_code,
            street_number,
            id_token,
            timeout=timeout,
            verify=verify,
        )
        if not address_list:
            _LOGGER.error("Burgerportaal: Unable to fetch address list!")
            return []

        address_id = _select_address_id(address_list, suffix)
        if not address_id:
            _LOGGER.warning("Burgerportaal: Address not found!")
            return []

        waste_data_raw_temp = _fetch_waste_data_raw_temp(
            session,
            org_id,
            address_id,
            id_token,
            timeout=timeout,
            verify=verify,
        )

        waste_data_raw = _parse_waste_data_raw(waste_data_raw_temp)
        return waste_data_raw

    except requests.exceptions.RequestException as err:
        _LOGGER.error("Burgerportaal request error: %s", err)
        raise ValueError(err) from err
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("Burgerportaal: Invalid and/or no data received")
        raise ValueError("Invalid and/or no data received from Burgerportaal") from err
