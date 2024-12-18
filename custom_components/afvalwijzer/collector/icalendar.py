from datetime import datetime
import re
import requests

from ..common.main_functions import _waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_ICALENDAR


def get_waste_data_raw(provider, postal_code, street_number, suffix):
    DATE_PATTERN = re.compile(r"^\d{8}")
    today = datetime.now()

    if provider not in SENSOR_COLLECTORS_ICALENDAR:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    try:
        url = SENSOR_COLLECTORS_ICALENDAR[provider].format(
            provider,
            postal_code,
            street_number,
            suffix,
            today.strftime("%Y-%m-%d"),
            today.year,
        )
        raw_response = requests.get(url, timeout=60, verify=False)
        raw_response.raise_for_status()  # Raise an error for bad responses
    except requests.exceptions.RequestException as err:
        raise ValueError(f"Error in request to {url}: {err}") from err

    try:
        response = raw_response.text
    except ValueError as err:
        raise ValueError(f"Invalid or no data received from {url}: {err}") from err

    if not response:
        _LOGGER.error("No waste data found!")
        return []

    waste_data_raw = []
    waste_date = None
    waste_type = None

    for line in response.splitlines():
        key_value = line.split(":", 2)
        field = key_value[0].split(";")[0]

        if field == "BEGIN" and key_value[1] == "VEVENT":
            waste_date = None
            waste_type = None
        elif field == "SUMMARY":
            waste_type = _waste_type_rename(key_value[1].strip().lower())
        elif field == "DTSTART":
            if DATE_PATTERN.match(key_value[1]):
                waste_date = f"{key_value[1][:4]}-{key_value[1][4:6]}-{key_value[1][6:8]}"
            else:
                _LOGGER.debug(f"Unsupported waste_date format: {key_value[1]}")
        elif field == "END" and key_value[1] == "VEVENT":
            if waste_date and waste_type:
                waste_data_raw.append({"type": waste_type, "date": waste_date})
            else:
                _LOGGER.debug(
                    f"No waste_date or waste_type extracted from event: waste_date={waste_date}, waste_type={waste_type}"
                )

    return waste_data_raw



