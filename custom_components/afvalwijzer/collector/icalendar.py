from datetime import datetime
import re
import requests

from ..common.main_functions import waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_ICALENDAR


def get_waste_data_raw(provider, postal_code, street_number, suffix):
    DATE_PATTERN = re.compile(r"^\d{8}")
    today = datetime.now()

    if provider not in SENSOR_COLLECTORS_ICALENDAR:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    # Construct URL using the provider template
    url = SENSOR_COLLECTORS_ICALENDAR[provider].format(
        provider,
        postal_code,
        street_number,
        suffix,
        today.strftime("%Y-%m-%d"),
        today.year,
    )

    try:
        raw_response = requests.get(url, timeout=60, verify=False)
        raw_response.raise_for_status()  # Raise error for non-200 responses
    except requests.exceptions.RequestException as err:
        raise ValueError(f"Error in request to {url}: {err}") from err

    response_text = raw_response.text
    if not response_text:
        _LOGGER.error("No waste data found!")
        return []

    waste_data_raw = []
    event = {}  # Temporary dict to hold event data

    for line in response_text.splitlines():
        # Only process lines containing a colon
        if ":" not in line:
            continue

        # Split the line into field and value parts
        parts = line.split(":", 1)
        if len(parts) < 2:
            continue

        # Clean up the field name and value
        field = parts[0].split(";")[0].strip()
        value = parts[1].strip()

        if field == "BEGIN" and value == "VEVENT":
            event = {}  # Initialize a new event
        elif field == "SUMMARY":
            event["type"] = waste_type_rename(value.lower())
        elif field == "DTSTART":
            if DATE_PATTERN.match(value):
                # Format date as YYYY-MM-DD
                event["date"] = f"{value[:4]}-{value[4:6]}-{value[6:8]}"
            else:
                _LOGGER.debug(f"Unsupported waste_date format: {value}")
        elif field == "END" and value == "VEVENT":
            if "date" in event and "type" in event:
                waste_data_raw.append(event)
            else:
                _LOGGER.debug(f"Incomplete event data encountered: {event}")
            event = {}  # Reset the event for the next one

    return waste_data_raw
