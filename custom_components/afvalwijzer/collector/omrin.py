"""Afvalwijzer omrin."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
import logging
from typing import Any
import uuid

import requests

from ..common.main_functions import format_postal_code, waste_type_rename
from ..const.const import SENSOR_COLLECTORS_OMRIN

_LOGGER = logging.getLogger(__name__)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 30.0)

# Placeholder date Omrin returns for entries without a pickup.
_EMPTY_DATE_PREFIX = "0001-01-01"

# Refresh the access token when it expires within this margin.
_TOKEN_EXPIRY_MARGIN = timedelta(minutes=1)

# Auth state (device id, tokens) per address, kept for the lifetime of the process
# so a refresh does not register a new device every time.
_AUTH_CACHE: dict[str, dict[str, Any]] = {}


def _build_url(provider: str, postal_code: str, house_number: str, suffix: str) -> str:
    if provider not in SENSOR_COLLECTORS_OMRIN:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    corrected_postal_code = format_postal_code(postal_code)

    return SENSOR_COLLECTORS_OMRIN[provider].format(
        corrected_postal_code,
        house_number,
        suffix,
    )


def _normalize_token(token: str | None) -> str | None:
    """Allow passing either a raw token or 'Bearer <token>'."""
    if not token:
        return None
    token = token.strip()
    if not token:
        return None
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token or None


def _parse_expiry(value: str | None) -> datetime | None:
    """Parse an ISO expiry timestamp into a naive UTC datetime."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        _LOGGER.warning("Omrin: failed to parse token expiry: %s", value)
        return None
    if parsed.tzinfo:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _auth_from_response(
    data: dict[str, Any], device_id: str, action: str
) -> dict[str, Any]:
    """Build an auth state from a login or refresh response."""
    if not (data.get("success") and data.get("data")):
        raise ValueError(f"{action} failed: {data.get('errors', 'Unknown error')}")

    payload = data["data"]
    token = payload.get("accessToken")
    if not token:
        raise ValueError("Not logged in")

    return {
        "device_id": device_id,
        "token": token,
        "refresh_token": payload.get("refreshToken"),
        "expires_at": _parse_expiry(payload.get("expiresAt")),
    }


def _login(
    session: requests.Session,
    url: str,
    postal_code: str,
    house_number: str,
    suffix: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
    device_id: str | None = None,
) -> dict[str, Any]:
    device_id = device_id or str(uuid.uuid4())
    payload = {
        "Email": None,
        "Password": None,
        # keep original behavior: use raw input postal_code here
        "PostalCode": postal_code,
        "HouseNumber": int(house_number),
        "HouseNumberExtension": suffix or None,
        "DeviceId": device_id,
        "Platform": "iOS",
        "AppVersion": "4.0.3.273",
        "OsVersion": "iPhone15,3 26.2.1",
    }

    response = session.post(
        f"{url}/api/auth/login",
        json=payload,
        headers={
            "User-Agent": "Omrin.Afvalapp.Client/1.0",
            "Accept": "application/json",
        },
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()

    data = response.json() if response.content else {}
    return _auth_from_response(data, device_id, "Login")


def _refresh(
    session: requests.Session,
    url: str,
    auth: dict[str, Any],
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> dict[str, Any]:
    """Exchange the refresh token for a new access token (the refresh token rotates)."""
    if not auth.get("token") or not auth.get("refresh_token"):
        raise ValueError("Cannot refresh: missing token or refresh token")

    response = session.post(
        f"{url}/api/auth/refreshtoken",
        json={"Token": auth["token"], "RefreshToken": auth["refresh_token"]},
        headers={
            "User-Agent": "Omrin.Afvalapp.Client/1.0",
            "Accept": "application/json",
        },
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()

    data = response.json() if response.content else {}
    return _auth_from_response(data, auth["device_id"], "Token refresh")


def _is_unauthorized(err: requests.exceptions.HTTPError) -> bool:
    return err.response is not None and err.response.status_code == 401


def _is_expiring(auth: dict[str, Any]) -> bool:
    expires_at = auth.get("expires_at")
    return (
        bool(expires_at)
        and expires_at - datetime.now(UTC).replace(tzinfo=None) < _TOKEN_EXPIRY_MARGIN
    )


def _get_auth(
    session: requests.Session,
    url: str,
    cache_key: str,
    *,
    postal_code: str,
    house_number: str,
    suffix: str,
    timeout: tuple[float, float],
    verify: bool,
    device_id: str | None,
) -> dict[str, Any]:
    """Return a usable auth state: cached, refreshed, or a fresh login."""
    auth = _AUTH_CACHE.get(cache_key)

    if auth and _is_expiring(auth):
        _LOGGER.debug("Omrin: token expiring soon, refreshing")
        try:
            auth = _refresh(session, url, auth, timeout=timeout, verify=verify)
            _AUTH_CACHE[cache_key] = auth
        except requests.exceptions.HTTPError as err:
            if not _is_unauthorized(err):
                raise
            _LOGGER.debug("Omrin: refresh token was rejected, logging in again")
            auth = None
        except ValueError:
            auth = None

    if not auth:
        previous = _AUTH_CACHE.get(cache_key) or {}
        auth = _login(
            session,
            url,
            postal_code,
            house_number,
            suffix,
            timeout=timeout,
            verify=verify,
            device_id=device_id or previous.get("device_id"),
        )
        _AUTH_CACHE[cache_key] = auth

    return auth


def _fetch_calendar(
    session: requests.Session,
    url: str,
    token: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> Sequence[dict[str, Any]]:
    query = """
    query FetchCalendar {
      fetchCalendar {
        id
        date
        description
        type
        containerType
        placingTime
        state
      }
    }
    """

    response = session.post(
        f"{url}/graphql",
        headers={
            "Content-Type": "application/json",
            "User-Agent": "GraphQL.Client/6.1.0.0",
            "Authorization": f"Bearer {token}",
        },
        json={"query": query},
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()

    result = response.json() if response.content else {}

    if result.get("errors"):
        error_messages = ", ".join(e.get("message", str(e)) for e in result["errors"])
        raise ValueError(f"GraphQL error: {error_messages}")

    return (result.get("data") or {}).get("fetchCalendar") or []


def _parse_waste_data_raw(
    waste_data_raw_temp: Sequence[dict[str, Any]],
    postal_code: str = "",
) -> list[dict[str, str]]:
    waste_data_raw: list[dict[str, str]] = []

    for item in waste_data_raw_temp:
        date_str = item.get("date")
        if not date_str or date_str.startswith(_EMPTY_DATE_PREFIX):
            continue

        raw_type = (item.get("type") or "").strip().lower()
        # "overig" (other) is Omrin's label for chemical waste (KCA).
        if raw_type == "overig":
            raw_type = "kca"

        waste_type = waste_type_rename(raw_type, postal_code)
        if not waste_type:
            continue

        # The API returns ISO datetimes (e.g. 2026-01-01T00:00:00), optionally with an offset.
        waste_date = datetime.fromisoformat(date_str.replace("Z", "+00:00")).strftime(
            "%Y-%m-%d"
        )
        waste_data_raw.append({"type": waste_type, "date": waste_date})

    return waste_data_raw


def get_waste_data_raw(
    provider: str,
    postal_code: str,
    house_number: str,
    suffix: str,
    *,
    token: str | None = None,
    session: requests.Session | None = None,
    timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = True,
    device_id: str | None = None,
) -> list[dict[str, str]]:
    """Return waste_data_raw."""

    url = _build_url(provider, postal_code, house_number, suffix)
    session = session or requests.Session()
    cache_key = f"{provider}_{format_postal_code(postal_code)}_{house_number}_{suffix}"

    try:
        token = _normalize_token(token)

        if token:
            _LOGGER.debug("Omrin: token supplied, skipping login")
            waste_data_raw_temp = _fetch_calendar(
                session, url, token, timeout=timeout, verify=verify
            )
        else:
            auth = _get_auth(
                session,
                url,
                cache_key,
                postal_code=postal_code,
                house_number=house_number,
                suffix=suffix,
                timeout=timeout,
                verify=verify,
                device_id=device_id,
            )
            try:
                waste_data_raw_temp = _fetch_calendar(
                    session, url, auth["token"], timeout=timeout, verify=verify
                )
            except requests.exceptions.HTTPError as err:
                if not _is_unauthorized(err):
                    raise
                _LOGGER.debug("Omrin: access token was rejected, logging in again")
                _AUTH_CACHE.pop(cache_key, None)
                auth = _get_auth(
                    session,
                    url,
                    cache_key,
                    postal_code=postal_code,
                    house_number=house_number,
                    suffix=suffix,
                    timeout=timeout,
                    verify=verify,
                    device_id=auth["device_id"],
                )
                waste_data_raw_temp = _fetch_calendar(
                    session, url, auth["token"], timeout=timeout, verify=verify
                )

        return _parse_waste_data_raw(waste_data_raw_temp, postal_code)

    except requests.exceptions.RequestException as err:
        _LOGGER.error("Omrin request error: %s", err)
        raise ValueError(err) from err
