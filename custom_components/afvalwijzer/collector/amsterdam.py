from __future__ import annotations

"""
Amsterdam collector (AMSTERDAM) for waste data from Amsterdam API.

This version is adapted to the "collector function" style used in your project:
- entrypoint: get_waste_data_raw(provider, postal_code, street_number, suffix)
- returns: waste_data_raw (list[{"type": <slug>, "date": "YYYY-MM-DD"}])
- keeps naming: waste_data_raw_temp -> waste_data_raw
- no async / no base classes / no HA models
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import requests
from urllib3.exceptions import InsecureRequestWarning

from ..const.const import _LOGGER, SENSOR_COLLECTORS_AMSTERDAM
from ..common.main_functions import waste_type_rename, format_postal_code


requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: Tuple[float, float] = (5.0, 60.0)

WEEKDAY_MAP: Dict[str, int] = {
    "maandag": 1,
    "dinsdag": 2,
    "woensdag": 3,
    "donderdag": 4,
    "vrijdag": 5,
    "zaterdag": 6,
    "zondag": 7,
}


def _build_url(provider: str) -> str:
    """
    Expects SENSOR_COLLECTORS_AMSTERDAM to be either:
      - dict[str, str] with provider->base_url, OR
      - dict with key "amsterdam" as fallback
    """
    if provider in SENSOR_COLLECTORS_AMSTERDAM:
        url = SENSOR_COLLECTORS_AMSTERDAM[provider]
    else:
        url = SENSOR_COLLECTORS_AMSTERDAM.get("amsterdam")

    if not url:
        raise ValueError(f"Invalid provider: {provider}, please verify")
    return url.rstrip("/")


def _parse_date(date_str: str, today: datetime) -> Optional[datetime]:
    """
    Parse Amsterdam date strings. The API sometimes returns:
      - dd-mm-yy
      - dd-mm-YYYY
      - dd-mm (no year)
    """
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


def _date_in_future(dates_list: List[datetime], current_date: datetime) -> List[datetime]:
    return [d for d in dates_list if d > current_date]


def _calculate_day_delta(week_day: int, today: datetime, frequency_type: Optional[str] = None) -> int:
    """
    week_day: ISO weekday (Mon=1 .. Sun=7)
    frequency_type: None / "even" / "oneven"
    """
    iso = today.isocalendar()
    current_week = iso[1]
    current_weekday = iso[2]
    is_even_week = (current_week % 2 == 0)

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

    # weekly
    if current_weekday > week_day:
        return (week_day - current_weekday) + 7
    return week_day - current_weekday


def _generate_dates_for_year(
    day_delta: int,
    week_interval: int,
    current_date: datetime,
    even_weeks: bool = False,
) -> List[datetime]:
    """
    Ported logic from the original collector. Kept as close as possible to preserve behavior.
    Generates dates for up to ~1 year.
    """
    dates: List[datetime] = []
    week_offset = 0

    while week_offset <= 52:
        date = current_date + timedelta(days=day_delta, weeks=week_offset)

        if week_interval > 1:
            # Handle 52/53-week year edge cases from original code
            week_num = date.isocalendar()[1]
            if ((week_num % 2 == 0) and not even_weeks) or ((week_num % 2 > 0) and even_weeks):
                date = date - timedelta(weeks=1)
                if dates and dates[-1] == date:
                    date = date + timedelta(weeks=2)
                    week_offset = week_offset + 1
                elif (date.isocalendar()[1] % 2 > 0) and even_weeks:
                    date = date + timedelta(weeks=2)
                    week_offset = week_offset + 2
                else:
                    week_offset = week_offset - 1

        dates.append(date)
        week_offset = week_offset + week_interval

    return dates


def _build_query_params(postal_code: str, street_number: str, suffix: str) -> List[Dict[str, str]]:
    """
    Returns a list of param dicts to try (suffix variations first).
    """
    base_params = {
        "postcode": postal_code,
        "huisnummer": str(street_number),
    }

    if not suffix:
        return [base_params]

    sfx = suffix.strip()
    # Try the same suffix variations as the original code.
    attempts = [
        {**base_params, "huisletter": sfx.lower()},
        {**base_params, "huisnummertoevoeging": sfx.lower()},
        {**base_params, "huisletter": sfx.upper()},
        {**base_params, "huisnummertoevoeging": sfx.upper()},
    ]
    # Add a final attempt with no suffix
    attempts.append(base_params)
    return attempts


def _check_response_is_valid(text: str) -> bool:
    # Original heuristic: "len(text) > 220"
    return len(text or "") > 220


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    base_url: str,
    params_list: List[Dict[str, str]],
    *,
    timeout: Tuple[float, float],
    verify: bool,
) -> Dict[str, Any]:
    """
    Tries multiple suffix variants; returns the JSON dict for the first valid response.
    Raises ValueError if none match.
    """
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

        # Keep original "validity check" behavior
        if _check_response_is_valid(response.text):
            return response.json()

    raise ValueError(f"Invalid and/or no data received from {last_url or base_url}")


def _is_item_valid(item: Dict[str, Any]) -> bool:
    """
    Ported logic (with guards) from the original collector.
    """
    freq = item.get("afvalwijzerAfvalkalenderFrequentie")
    waar = item.get("afvalwijzerWaar") or ""
    code = item.get("afvalwijzerFractieCode")
    days = item.get("afvalwijzerOphaaldagen")

    if not freq and not waar:
        return False
    if not freq and "stoep" not in waar:
        return False
    if not code or not days:
        return False
    return True


def _process_collection_dates(item: Dict[str, Any], today: datetime) -> List[datetime]:
    """
    Convert Amsterdam's frequency + weekday strings to concrete future dates.
    """
    collection_days = (item.get("afvalwijzerOphaaldagen") or "").replace(" ", "").split(",")
    future_dates: List[datetime] = []

    for day in collection_days:
        week_day = WEEKDAY_MAP.get(day)
        if not week_day:
            continue

        frequency = item.get("afvalwijzerAfvalkalenderFrequentie") or ""

        if not frequency:
            # Weekly
            day_delta = _calculate_day_delta(week_day, today)
            future_dates.extend(_generate_dates_for_year(day_delta, 1, today, False))
            continue

        if ("weken" in frequency) or ("week" in frequency):
            # Bi-weekly odd/even
            frequency_clean = frequency.replace(" weken", "").replace(" week", "").strip()
            day_delta = _calculate_day_delta(week_day, today, frequency_clean)
            is_even = frequency_clean == "even"
            future_dates.extend(_generate_dates_for_year(day_delta, 2, today, is_even))
            continue

        # Specific dates list
        date_strings = (
            frequency.replace(" ", ".")
            .replace("./", "")
            .replace(".", ",")
            .split(",")
        )
        dates: List[datetime] = []
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
    session: Optional[requests.Session] = None,
    timeout: Tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
) -> List[Dict[str, str]]:
    """
    AMSTERDAM collector in your project style.
    Returns:
      waste_data_raw: [{"type": <renamed_type>, "date": "YYYY-MM-DD"}, ...]
    """
    session = session or requests.Session()

    try:
        base_url = _build_url(provider)

        # Keep your typical formatting conventions
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

        waste_data_raw: List[Dict[str, str]] = []
        today = datetime.now()

        for item in embedded:
            if not _is_item_valid(item):
                continue

            code = (item.get("afvalwijzerFractieCode") or "").strip().lower()
            waste_type = waste_type_rename(code)
            if not waste_type:
                continue

            future_dates = _process_collection_dates(item, today)

            for date in future_dates:
                waste_date = date.replace(hour=0, minute=0, second=0, microsecond=0).strftime("%Y-%m-%d")
                waste_data_raw.append({"type": waste_type, "date": waste_date})

        # Keep deterministic output (nice for sensors)
        return sorted(waste_data_raw, key=lambda d: (d["date"], d["type"]))

    except requests.exceptions.RequestException as err:
        _LOGGER.error("AMSTERDAM request error: %s", err)
        raise ValueError(err) from err
    except (KeyError, TypeError, ValueError) as err:
        _LOGGER.error("AMSTERDAM: Invalid and/or no data received")
        raise ValueError("Invalid and/or no data received from AMSTERDAM") from err
