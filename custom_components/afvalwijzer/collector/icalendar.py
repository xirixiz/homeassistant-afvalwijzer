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

    TODAY = datetime.now()
    YEAR_CURRENT = TODAY.year
    try:
        url = SENSOR_COLLECTORS_ICALENDAR[provider].format(
            provider,
            postal_code,
            street_number,
            suffix,
            datetime.now().strftime("%Y-%m-%d"),
            YEAR_CURRENT,
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
    waste_date = None
    waste_type = None

    for line in response.splitlines():
        if provider == "veldhoven":
            key, value = line.split(":", 1)
        else:
            key, value = line.split(":", 2)
        field = key.split(";")[0]
        if field == "BEGIN" and value == "VEVENT":
            waste_date = None
            waste_type = None
        elif field == "SUMMARY":
            waste_type = _waste_type_rename(value.strip().lower())
        elif field == "DTSTART":
            if DATE_PATTERN.match(value):
                waste_date = f"{value[:4]}-{value[4:6]}-{value[6:8]}"
            else:
                _LOGGER.debug(f"Unsupported waste_date format: {value}")
        elif field == "END" and value == "VEVENT":
            if waste_date and waste_type:
                waste_data_raw.append({"type": waste_type, "date": waste_date})
            else:
                _LOGGER.debug(
                    f"No waste_date or waste_type extracted from event: waste_date={waste_date}, waste_type={waste_type}"
                )

    return waste_data_raw


if __name__ == "__main__":
    print("Yell something at a mountain!")
