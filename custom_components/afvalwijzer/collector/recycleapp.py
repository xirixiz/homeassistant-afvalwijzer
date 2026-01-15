"""Afvalwijzer integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..common.main_functions import format_postal_code, waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_RECYCLEAPP

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)

_BASE_URL = "https://www.recycleapp.be/api/app/v1/"
_X_SECRET = "Op2tDi2pBmh1wzeC5TaN2U3knZan7ATcfOQgxh4vqC0mDKmnPP2qzoQusmInpglfIkxx8SZrasBqi5zgMSvyHggK9j6xCQNQ8xwPFY2o03GCcQfcXVOyKsvGWLze7iwcfcgk2Ujpl0dmrt3hSJMCDqzAlvTrsvAEiaSzC9hKRwhijQAFHuFIhJssnHtDSB76vnFQeTCCvwVB27DjSVpDmq8fWQKEmjEncdLqIsRnfxLcOjGIVwX5V0LBntVbeiBvcjyKF2nQ08rIxqHHGXNJ6SbnAmTgsPTg7k6Ejqa7dVfTmGtEPdftezDbuEc8DdK66KDecqnxwOOPSJIN0zaJ6k2Ye2tgMSxxf16gxAmaOUqHS0i7dtG5PgPSINti3qlDdw6DTKEPni7X0rxM"
_X_CONSUMER = "recycleapp.be"


def _build_url(provider: str) -> str:
    """Build the base URL for the RecycleApp collector.

    Keep the project pattern:
    SENSOR_COLLECTORS_RECYCLEAPP = {"recycleapp": "https://www.recycleapp.be/api/app/v1/"}.
    """
    url = SENSOR_COLLECTORS_RECYCLEAPP.get(provider)
    if not url:
        raise ValueError(f"Invalid provider: {provider}, please verify")
    return url.rstrip("/") + "/"


def _build_headers(access_token: str) -> dict[str, str]:
    return {
        "x-secret": _X_SECRET,
        "x-consumer": _X_CONSUMER,
        "User-Agent": "",
        "Authorization": access_token or "",
    }


def _fetch_access_token(
    session: requests.Session,
    base_url: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> str:
    response = session.get(
        f"{base_url}access-token",
        headers=_build_headers(""),
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()

    data = response.json() or {}
    token = data.get("accessToken")
    if not token:
        raise ValueError("RecycleApp: accessToken missing in response")
    return token


def _fetch_postcode_id(
    session: requests.Session,
    base_url: str,
    access_token: str,
    postal_code: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> str:
    response = session.get(
        f"{base_url}zipcodes",
        params={"q": postal_code},
        headers=_build_headers(access_token),
        timeout=timeout,
        verify=verify,
    )

    # Original behavior: refresh token on 401 and retry once
    if response.status_code == 401:
        access_token = _fetch_access_token(
            session, base_url, timeout=timeout, verify=verify
        )
        response = session.get(
            f"{base_url}zipcodes",
            params={"q": postal_code},
            headers=_build_headers(access_token),
            timeout=timeout,
            verify=verify,
        )

    response.raise_for_status()
    data = response.json() or {}
    items = data.get("items") or []
    if not items or not items[0].get("id"):
        raise ValueError("RecycleApp: postcode_id not found")
    return str(items[0]["id"])


def _fetch_street_id(
    session: requests.Session,
    base_url: str,
    access_token: str,
    street_name: str,
    postcode_id: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> str:
    response = session.get(
        f"{base_url}streets",
        params={"q": street_name, "zipcodes": postcode_id},
        headers=_build_headers(access_token),
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()

    data = response.json() or {}
    items = data.get("items") or []
    if not items:
        raise ValueError("RecycleApp: street_id not found (no items)")

    # Original: exact name match if possible, else first item
    for item in items:
        if item.get("name") == street_name and item.get("id"):
            return str(item["id"])

    if items[0].get("id"):
        return str(items[0]["id"])

    raise ValueError("RecycleApp: street_id not found")


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    base_url: str,
    access_token: str,
    postcode_id: str,
    street_id: str,
    street_number: str,
    *,
    days_forward: int = 60,
    timeout: tuple[float, float],
    verify: bool,
) -> dict[str, Any]:
    startdate = datetime.now().strftime("%Y-%m-%d")
    enddate = (datetime.now() + timedelta(days=days_forward)).strftime("%Y-%m-%d")

    response = session.get(
        f"{base_url}collections",
        params={
            "zipcodeId": postcode_id,
            "streetId": street_id,
            "houseNumber": street_number,
            "fromDate": startdate,
            "untilDate": enddate,
            "size": "100",
        },
        headers=_build_headers(access_token),
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()
    return response.json() or {}


def _parse_waste_data_raw(waste_data_raw_temp: dict[str, Any]) -> list[dict[str, str]]:
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

        # Original: skip replaced items
        exception = item.get("exception") or {}
        if exception.get("replacedBy"):
            continue

        waste_type = waste_type_rename(name_nl)
        if not waste_type:
            continue

        waste_date = datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.000Z").strftime(
            "%Y-%m-%d"
        )
        waste_data_raw.append({"type": waste_type, "date": waste_date})

    return sorted(waste_data_raw, key=lambda d: (d["date"], d["type"]))


def get_waste_data_raw(
    provider: str,
    postal_code: str,
    street_number: str,
    suffix: str,
    *,
    street_name: str | None = None,
    access_token: str | None = None,
    session: requests.Session | None = None,
    timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
) -> list[dict[str, str]]:
    """Return waste_data_raw."""

    session = session or requests.Session()

    try:
        base_url = _build_url(provider)
        postal_code = format_postal_code(postal_code)

        if not street_name:
            _LOGGER.error("RECYCLEAPP: street_name is required")
            return []

        # Token reuse requirement
        if not access_token:
            access_token = _fetch_access_token(
                session, base_url, timeout=timeout, verify=verify
            )

        postcode_id = _fetch_postcode_id(
            session,
            base_url,
            access_token,
            postal_code,
            timeout=timeout,
            verify=verify,
        )

        street_id = _fetch_street_id(
            session,
            base_url,
            access_token,
            street_name,
            postcode_id,
            timeout=timeout,
            verify=verify,
        )

        waste_data_raw_temp = _fetch_waste_data_raw_temp(
            session,
            base_url,
            access_token,
            postcode_id,
            street_id,
            str(street_number),
            timeout=timeout,
            verify=verify,
        )

        if not waste_data_raw_temp:
            _LOGGER.error("No Waste data found!")
            return []

        waste_data_raw = _parse_waste_data_raw(waste_data_raw_temp)
        return waste_data_raw

    except requests.exceptions.RequestException as err:
        _LOGGER.error("RECYCLEAPP request error: %s", err)
        raise ValueError(err) from err
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("RECYCLEAPP: Invalid and/or no data received")
        raise ValueError("Invalid and/or no data received from RECYCLEAPP") from err
