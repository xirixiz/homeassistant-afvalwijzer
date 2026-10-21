"""Afvalwijzer opzet."""

from __future__ import annotations

from datetime import date, datetime
from html import unescape
import logging
import re
from typing import Any

import requests

from ..common.main_functions import waste_type_rename
from ..const.const import SENSOR_COLLECTORS_OPZET

_LOGGER = logging.getLogger(__name__)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)
_BAG_ID_CACHE: dict[str, str] = {}


def _build_base_url(provider: str) -> str:
    if provider not in SENSOR_COLLECTORS_OPZET:
        raise ValueError(f"Invalid provider: {provider}, please verify")
    return SENSOR_COLLECTORS_OPZET[provider]


def _fetch_address_list(
    session: requests.Session,
    base_url: str,
    postal_code: str,
    house_number: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> list[dict[str, Any]]:
    url_address = f"{base_url}/rest/adressen/{postal_code}-{house_number}"
    response = session.get(url_address, timeout=timeout, verify=verify)
    response.raise_for_status()
    data = response.json()
    return data or []


def _select_bag_id(
    response_address: list[dict[str, Any]],
    suffix: str,
) -> str | None:
    if not response_address:
        return None

    # Original behavior: if multiple and suffix, match huisletter or huisnummerToevoeging
    if len(response_address) > 1 and suffix:
        for item in response_address:
            if (
                item.get("huisletter") == suffix
                or item.get("huisnummerToevoeging") == suffix
            ):
                return item.get("bagId")
        return None

    return response_address[0].get("bagId")


def _get_bag_id(
    session: requests.Session,
    base_url: str,
    postal_code: str,
    house_number: str,
    suffix: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> str | None:
    cache_key = f"{base_url}_{postal_code}_{house_number}_{suffix}"
    if cache_key in _BAG_ID_CACHE:
        return _BAG_ID_CACHE[cache_key]

    response_address = _fetch_address_list(
        session, base_url, postal_code, house_number, timeout=timeout, verify=verify
    )
    if not response_address:
        return None

    bag_id = _select_bag_id(response_address, suffix)
    if bag_id:
        _BAG_ID_CACHE[cache_key] = bag_id
    return bag_id


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    base_url: str,
    bag_id: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> list[dict[str, Any]]:
    url_waste = f"{base_url}/rest/adressen/{bag_id}/afvalstromen"
    response = session.get(url_waste, timeout=timeout, verify=verify)
    response.raise_for_status()
    data = response.json()
    return data or []


def _fetch_calendar_raw_temp(
    session: requests.Session,
    base_url: str,
    bag_id: str,
    year: int,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> list[dict[str, Any]]:
    """Fetch the full-year calendar; return an empty list if it is unavailable.

    The calendar endpoint is what the municipalities' own websites use. Not every
    Opzet instance offers it, and next year's calendar may not be published yet.
    """
    url_calendar = f"{base_url}/rest/adressen/{bag_id}/kalender/{year}"
    try:
        response = session.get(url_calendar, timeout=timeout, verify=verify)
        if response.status_code != 200:
            return []
        data = response.json()
    except (requests.exceptions.RequestException, ValueError) as err:
        _LOGGER.debug("OPZET: calendar for %s not available: %s", year, err)
        return []

    return data if isinstance(data, list) else []


def _calendar_as_waste_data(
    calendar: list[dict[str, Any]],
    waste_streams: list[dict[str, Any]],
    today: date,
) -> list[dict[str, Any]]:
    """Turn calendar entries into the shape of the waste streams (title and date).

    Entries that can't be used (not an object, unknown stream, missing or invalid
    date, in the past) are skipped, so one bad entry doesn't cost the rest.
    """
    titles = {
        stream.get("id"): stream.get("menu_title")
        for stream in waste_streams
        if isinstance(stream, dict)
    }

    items: list[dict[str, Any]] = []
    for entry in calendar:
        if not isinstance(entry, dict):
            continue

        title = titles.get(entry.get("afvalstroom_id"))
        date_str = entry.get("ophaaldatum")
        if not title or not date_str:
            continue

        try:
            entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except (TypeError, ValueError):
            _LOGGER.debug("OPZET: skipping calendar entry with invalid date: %r", entry)
            continue

        if entry_date >= today:
            items.append({"menu_title": title, "ophaaldatum": date_str})

    return items


def _parse_waste_data_raw(
    waste_data_raw_temp: list[dict[str, Any]],
    postal_code: str = "",
) -> list[dict[str, str]]:
    waste_data_raw: list[dict[str, str]] = []

    for item in waste_data_raw_temp:
        date_str = item.get("ophaaldatum")
        if not date_str:
            continue

        waste_type = waste_type_rename(
            (item.get("menu_title") or "").strip().lower(), postal_code
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
    suffix = (suffix or "").strip().upper()

    base_url = _build_base_url(provider)

    try:
        bag_id = _get_bag_id(
            session,
            base_url,
            postal_code,
            house_number,
            suffix,
            timeout=timeout,
            verify=verify,
        )
        if not bag_id:
            _LOGGER.warning("Address/bag_id not found!")
            return []

        waste_data_raw_temp = _fetch_waste_data_raw_temp(
            session,
            base_url,
            bag_id,
            timeout=timeout,
            verify=verify,
        )

        # The waste streams only hold the next pickup per stream. Add the calendar for
        # this and next year, so the schedule covers more than the next pickup. A
        # stream the calendar leaves out still keeps its next pickup.
        today = datetime.now().date()
        calendar_items: list[dict[str, Any]] = []
        for year in (today.year, today.year + 1):
            calendar_items.extend(
                _calendar_as_waste_data(
                    _fetch_calendar_raw_temp(
                        session,
                        base_url,
                        bag_id,
                        year,
                        timeout=timeout,
                        verify=verify,
                    ),
                    waste_data_raw_temp,
                    today,
                )
            )

        waste_data_raw: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for entry in _parse_waste_data_raw(
            waste_data_raw_temp + calendar_items, postal_code
        ):
            key = (entry["type"], entry["date"])
            if key not in seen:
                seen.add(key)
                waste_data_raw.append(entry)

        return waste_data_raw

    except requests.exceptions.RequestException as err:
        _LOGGER.error("OPZET request error: %s", err)
        raise ValueError(err) from err
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("OPZET: Invalid and/or no data received from %s", base_url)
        raise ValueError(f"Invalid and/or no data received from {base_url}") from err


def _fetch_notification_data_raw_temp(
    session: requests.Session,
    base_url: str,
    bag_id: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> list[dict[str, Any]]:
    """Fetch raw notification data from the API."""
    url_notification = f"{base_url}/rest/app/meldingen/{bag_id}"
    response = session.get(url_notification, timeout=timeout, verify=verify)
    response.raise_for_status()
    data = response.json()
    return data or []


def _parse_notification_data_raw(
    notification_data_raw_temp: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Parse and clean notification data."""
    notification_data_raw: list[dict[str, Any]] = []

    for item in notification_data_raw_temp:
        content = item.get("content")
        if not content:
            continue

        # Strip HTML tags and decode HTML entities
        clean_content = re.sub(r"<[^>]*>", "", content)
        clean_content = unescape(clean_content).strip()

        if not clean_content:
            continue

        notification_data_raw.append(
            {
                "id": item.get("id"),
                "title": item.get("kop", ""),
                "content": clean_content,
                "dismissable": bool(item.get("afwijsbaar", 0)),
            }
        )

    return notification_data_raw


def get_notification_data_raw(
    provider: str,
    postal_code: str,
    house_number: str,
    suffix: str,
    *,
    session: requests.Session | None = None,
    timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = True,
) -> list[dict[str, Any]]:
    """Collector-style function for fetching notification data.

    Returns a list of notification dictionaries with id, title, content, and dismissable fields.
    Returns empty list if provider doesn't support notifications or if there are no notifications.
    """
    session = session or requests.Session()
    suffix = (suffix or "").strip().upper()
    base_url = _build_base_url(provider)

    try:
        bag_id = _get_bag_id(
            session,
            base_url,
            postal_code,
            house_number,
            suffix,
            timeout=timeout,
            verify=verify,
        )
        if not bag_id:
            _LOGGER.debug("No bag_id found for notifications")
            return []

        notification_data_raw_temp = _fetch_notification_data_raw_temp(
            session,
            base_url,
            bag_id,
            timeout=timeout,
            verify=verify,
        )

        notification_data_raw = _parse_notification_data_raw(notification_data_raw_temp)
        _LOGGER.debug(
            "Retrieved %s notification(s) from %s", len(notification_data_raw), provider
        )

        return notification_data_raw

    except requests.exceptions.RequestException as err:
        _LOGGER.warning("OPZET notification request error: %s", err)
        return []
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.warning("OPZET: Invalid notification data from %s: %s", base_url, err)
        return []
