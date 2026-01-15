"""Afvalwijzer integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from html import unescape
import re

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..common.main_functions import format_postal_code
from ..const.const import _LOGGER, SENSOR_COLLECTORS_MIJNAFVALWIJZER

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)


def _build_url(
    provider: str,
    postal_code: str,
    street_number: str,
    suffix: str,
) -> str:
    if provider not in SENSOR_COLLECTORS_MIJNAFVALWIJZER:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    corrected_postal_code = format_postal_code(postal_code)

    return SENSOR_COLLECTORS_MIJNAFVALWIJZER[provider].format(
        corrected_postal_code,
        street_number,
        suffix,
    )


def _fetch_data(
    session: requests.Session,
    url: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> dict:
    response = session.get(
        url,
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()
    return response.json()


def _parse_waste_data_raw(response: dict) -> list[dict]:
    ophaaldagen_data = response.get("ophaaldagen", {}).get("data", [])
    ophaaldagen_next_data = response.get("ophaaldagenNext", {}).get("data", [])

    if not ophaaldagen_data and not ophaaldagen_next_data:
        raise KeyError("No 'ophaaldagen' data found")

    # Keep original behavior: limit next items to 25
    return ophaaldagen_data + ophaaldagen_next_data[:25]


def get_waste_data_raw(
    provider: str,
    postal_code: str,
    street_number: str,
    suffix: str,
    *,
    session: requests.Session | None = None,
    timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
) -> list[dict]:
    """Return waste_data_raw."""

    session = session or requests.Session()
    url = _build_url(provider, postal_code, street_number, suffix)

    # Add afvaldata parameter to get afvaldata only from today onwards; this reduces the response size
    url = f"{url}&afvaldata={datetime.now().strftime('%Y-%m-%d')}"

    try:
        response = _fetch_data(
            session,
            url,
            timeout=timeout,
            verify=verify,
        )

        waste_data_raw = _parse_waste_data_raw(response)

        return waste_data_raw

    except requests.exceptions.RequestException as err:
        _LOGGER.error("MijnAfvalWijzer request error: %s", err)
        raise ValueError(err) from err
    except KeyError as err:
        _LOGGER.error("MijnAfvalWijzer invalid response from %s", url)
        raise KeyError(f"Invalid and/or no data received from {url}") from err


def _parse_notification_data_raw(response: dict) -> list[dict]:
    """Parse notification data from the 'mededelingen' response."""
    mededelingen_data = response.get("data", {}).get("mededelingen", {}).get("data", [])

    if not mededelingen_data:
        _LOGGER.debug("No 'mededelingen' data found in response")
        return []

    # Set cutoff date to only show actual notifications
    cutoff_date = datetime.now().date() - timedelta(days=30)

    notification_data_raw: list[dict] = []

    for item in mededelingen_data:
        start_date_str = item.get("start_date", "")
        if start_date_str and start_date_str != "0000-00-00":
            try:
                start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
                if start_date < cutoff_date:
                    _LOGGER.debug(
                        f"Skipping old notification: {item.get('title')} (start_date: {start_date_str})"
                    )
                    continue
            except ValueError:
                _LOGGER.warning(f"Invalid start_date format: {start_date_str}")
                # If date parsing fails, include the notification anyway

        content = item.get("text")
        if not content:
            continue

        # Strip HTML tags and decode HTML entities
        clean_content = re.sub("<[^<]+?>", "", content)
        clean_content = unescape(clean_content).strip()
        clean_content = " ".join(clean_content.split())

        if not clean_content:
            continue

        notification_data_raw.append(
            {
                "id": item.get("id"),
                "title": item.get("title", ""),
                "content": clean_content,
                "position": item.get("position"),
                "description": item.get("description", ""),
                "date": item.get("date", ""),
                "start_date": item.get("start_date", ""),
                "expiration_date": item.get("expiration_date", ""),
            }
        )

    return notification_data_raw


def get_notification_data_raw(
    provider: str,
    postal_code: str,
    street_number: str,
    suffix: str,
    *,
    session: requests.Session | None = None,
    timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
) -> list[dict]:
    """Collector-style function for fetching notification data.

    Returns a list of notification dictionaries with id, title, content, description and other fields.
    Returns empty list if provider doesn't support notifications or if there are no notifications.
    """
    session = session or requests.Session()
    url = _build_url(provider, postal_code, street_number, suffix)

    try:
        response = _fetch_data(
            session,
            url,
            timeout=timeout,
            verify=verify,
        )

        notification_data_raw = _parse_notification_data_raw(response)
        _LOGGER.debug(
            f"Retrieved {len(notification_data_raw)} notification(s) from {provider}"
        )

        return notification_data_raw

    except requests.exceptions.RequestException as err:
        _LOGGER.warning(f"MijnAfvalWijzer notification request error: {err}")
        return []
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.warning(f"MijnAfvalWijzer: Invalid notification data from {url}: {err}")
        return []
