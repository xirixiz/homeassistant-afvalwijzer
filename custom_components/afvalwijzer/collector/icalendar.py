from datetime import datetime
import re

import requests

from ..common.main_functions import _waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_ICALENDAR


def get_waste_data_raw(
    provider,
    postal_code,
    street_number,
    suffix,
):
    if provider not in SENSOR_COLLECTORS_ICALENDAR.keys():
        raise ValueError(f"Invalid provider: {provider}, please verify")

    DATE_PATTERN = re.compile(r"^\d{8}")

    try:
        url = SENSOR_COLLECTORS_ICALENDAR[provider].format(
            provider,
            postal_code,
            street_number,
            suffix,
            datetime.now().strftime("%Y-%m-%d"),
        )
        raw_response = requests.get(url, timeout=60, verify=False)
    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err

    try:
        response = raw_response.text
    except ValueError as err:
        raise ValueError(f"Invalid and/or no data received from {url}") from err

    if not response:
        _LOGGER.error("No waste data found!")
        return

    waste_data_raw = []
    date = None
    type = None

    for line in response.splitlines():
        key, value = line.split(":", 2)
        field = key.split(";")[0]
        if field == "BEGIN" and value == "VEVENT":
            date = None
            type = None
        elif field == "SUMMARY":
            type = value.strip().lower()
        elif field == "DTSTART":
            if DATE_PATTERN.match(value):
                date = f"{value[:4]}-{value[4:6]}-{value[6:8]}"
            else:
                _LOGGER.debug(f"Unsupported date format: {value}")
        elif field == "END" and value == "VEVENT":
            if date and type:
                waste_data_raw.append({"type": type, "date": date})
            else:
                _LOGGER.debug(
                    f"No date or type extracted from event: date={date}, type={type}"
                )

    return waste_data_raw


if __name__ == "__main__":
    print("Yell something at a mountain!")
