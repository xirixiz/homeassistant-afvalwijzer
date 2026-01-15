"""Afvalwijzer integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..common.main_functions import format_postal_code, waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_AMSTERDAM

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 60.0)

WEEKDAY_MAP: dict[str, int] = {
    "maandag": 1,
    "dinsdag": 2,
    "woensdag": 3,
    "donderdag": 4,
    "vrijdag": 5,
    "zaterdag": 6,
    "zondag": 7,
}


def _build_url(provider: str) -> str:
    """Build the base URL for the Amsterdam collector."""
    if provider in SENSOR_COLLECTORS_AMSTERDAM:
        url = SENSOR_COLLECTORS_AMSTERDAM[provider]
    else:
        url = SENSOR_COLLECTORS_AMSTERDAM.get("amsterdam")

    if not url:
        raise ValueError(f"Invalid provider: {provider}, please verify")
    return url.rstrip("/")


def _parse_date(date_str: str, today: datetime) -> datetime | None:
    """Parse Amsterdam date strings into datetime objects."""
    date_str = (date_str or "").strip()
    if not date_str:
        return None

    for fmt in ("%d-%m-%y", "%d-%m-%Y", "%d-%m"):
        try:
            parsed = datetime.strptime(date_str, fmt)
            if fmt == "%d-%m":
                parsed = datetime(today.year, parsed.month, parsed.day)
            return parsed
        except ValueError:
            continue

    _LOGGER.error("AMSTERDAM: Unable to process date: %s", date_str)
    return None


def _date_in_future(
    dates_list: list[datetime], current_date: datetime
) -> list[datetime]:
    return [d for d in dates_list if d > current_date]


def _calculate_day_delta(
    week_day: int, today: datetime, frequency_type: str | None = None
) -> int:
    """Calculate the day delta based on weekday and frequency."""
    iso = today.isocalendar()
    current_week = iso[1]
    current_weekday = iso[2]
    is_even_week = current_week % 2 == 0

    if frequency_type == "oneven":
        if is_even_week:
            return (week_day - current_weekday) + 7
        if current_weekday > week_day:
            return (week_day - current_weekday) + 14
        return week_day - current_weekday

    if frequency_type == "even":
        if not is_even_week:
            return (week_day - current_weekday) + 7
        if current_weekday > week_day:
            return (week_day - current_weekday) + 14
        return week_day - current_weekday

    if current_weekday > week_day:
        return (week_day - current_weekday) + 7
    return week_day - current_weekday


def _generate_dates_for_year(
    day_delta: int,
    week_interval: int,
    current_date: datetime,
    even_weeks: bool = False,
) -> list[datetime]:
    """Generate collection dates for roughly one year."""
    dates: list[datetime] = []
    week_offset = 0

    while week_offset <= 52:
        date = current_date + timedelta(days=day_delta, weeks=week_offset)

        if week_interval > 1:
            week_num = date.isocalendar()[1]
            if ((week_num % 2 == 0) and not even_weeks) or (
                (week_num % 2 > 0) and even_weeks
            ):
                date = date - timedelta(weeks=1)
                if dates and dates[-1] == date:
                    date = date + timedelta(weeks=2)
                    week_offset += 1
                elif (date.isocalendar()[1] % 2 > 0) and even_weeks:
                    date = date + timedelta(weeks=2)
                    week_offset += 2
                else:
                    week_offset -= 1

        dates.append(date)
        week_offset += week_interval

    return dates


def _build_query_params(
    postal_code: str, street_number: str, suffix: str
) -> list[dict[str, str]]:
    """Build query parameter variants for suffix handling."""
    base_params = {
        "postcode": postal_code,
        "huisnummer": str(street_number),
    }

    if not suffix:
        return [base_params]

    sfx = suffix.strip()
    attempts = [
        {**base_params, "huisletter": sfx.lower()},
        {**base_params, "huisnummertoevoeging": sfx.lower()},
        {**base_params, "huisletter": sfx.upper()},
        {**base_params, "huisnummertoevoeging": sfx.upper()},
        base_params,
    ]
    return attempts


def _check_response_is_valid(text: str) -> bool:
    return bool(text) and len(text) > 220


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    base_url: str,
    params_list: list[dict[str, str]],
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> dict[str, Any]:
    """Fetch raw waste data using multiple suffix variants."""
    last_url = None

    for params in params_list:
        response = session.get(
            f"{base_url}/",
            params=params,
            timeout=timeout,
            verify=verify,
        )
        response.raise_for_status()
        last_url = str(response.url)

        if _check_response_is_valid(response.text):
            return response.json()

    raise ValueError(f"Invalid and/or no data received from {last_url or base_url}")


def _is_item_valid(item: dict[str, Any]) -> bool:
    """Validate a single API item."""
    freq = item.get("afvalwijzerAfvalkalenderFrequentie")
    waar = item.get("afvalwijzerWaar") or ""
    code = item.get("afvalwijzerFractieCode")
    days = item.get("afvalwijzerOphaaldagen")

    return bool(freq or ("stoep" in waar)) and bool(code and days)


def _process_collection_dates(item: dict[str, Any], today: datetime) -> list[datetime]:
    """Convert frequency and weekday data into future dates."""
    collection_days = (
        (item.get("afvalwijzerOphaaldagen") or "").replace(" ", "").split(",")
    )
    future_dates: list[datetime] = []

    for day in collection_days:
        week_day = WEEKDAY_MAP.get(day)
        if not week_day:
            continue

        frequency = item.get("afvalwijzerAfvalkalenderFrequentie") or ""

        if not frequency:
            day_delta = _calculate_day_delta(week_day, today)
            future_dates.extend(_generate_dates_for_year(day_delta, 1, today))
            continue

        if "week" in frequency:
            frequency_clean = (
                frequency.replace(" weken", "").replace(" week", "").strip()
            )
            day_delta = _calculate_day_delta(week_day, today, frequency_clean)
            is_even = frequency_clean == "even"
            future_dates.extend(_generate_dates_for_year(day_delta, 2, today, is_even))
            continue

        date_strings = (
            frequency.replace(" ", ".").replace("./", "").replace(".", ",").split(",")
        )
        dates: list[datetime] = []
        for date_str in date_strings:
            parsed = _parse_date(date_str, today)
            if parsed:
                dates.append(parsed)
        future_dates.extend(_date_in_future(dates, today))

    return future_dates


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

    try:
        base_url = _build_url(provider)
        postal_code = format_postal_code(postal_code)
        suffix = (suffix or "").strip()

        params_list = _build_query_params(postal_code, str(street_number), suffix)

        waste_data_raw_temp = _fetch_waste_data_raw_temp(
            session,
            base_url,
            params_list,
            timeout=timeout,
            verify=verify,
        )

        embedded = (waste_data_raw_temp.get("_embedded") or {}).get("afvalwijzer") or []
        if not embedded:
            _LOGGER.error("No Waste data found!")
            return []

        waste_data_raw: list[dict[str, str]] = []
        today = datetime.now()

        for item in embedded:
            if not _is_item_valid(item):
                continue

            code = (item.get("afvalwijzerFractieCode") or "").strip().lower()
            waste_type = waste_type_rename(code)
            if not waste_type:
                continue

            waste_data_raw.extend(
                {
                    "type": waste_type,
                    "date": date.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    ).strftime("%Y-%m-%d"),
                }
                for date in _process_collection_dates(item, today)
            )

        return sorted(waste_data_raw, key=lambda d: (d["date"], d["type"]))

    except requests.exceptions.RequestException as err:
        _LOGGER.error("AMSTERDAM request error: %s", err)
        raise ValueError(err) from err
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("AMSTERDAM: Invalid and/or no data received")
        raise ValueError("Invalid and/or no data received from AMSTERDAM") from err
