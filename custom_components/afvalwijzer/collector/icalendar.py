from datetime import datetime
import re
import requests

from ..common.main_functions import _waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_ICALENDAR


def get_waste_data_raw(provider, postal_code, street_number, suffix):
    validate_provider(provider)

    try:
        url = build_url(provider, postal_code, street_number, suffix)
        raw_response = requests.get(url, timeout=60, verify=False)
        raw_response.raise_for_status()
    except requests.exceptions.RequestException as err:
        handle_request_exception(err)

    try:
        response = raw_response.text
    except ValueError as err:
        handle_invalid_data(url, err)

    if not response:
        _LOGGER.error("No waste data found!")
        return

    return parse_response(response)


def validate_provider(provider):
    if provider not in SENSOR_COLLECTORS_ICALENDAR.keys():
        raise ValueError(f"Invalid provider: {provider}, please verify")


def build_url(provider, postal_code, street_number, suffix):
    return SENSOR_COLLECTORS_ICALENDAR[provider].format(
        provider,
        postal_code,
        street_number,
        suffix,
        datetime.now().strftime("%Y-%m-%d"),
    )


def handle_request_exception(err):
    raise ValueError(err) from err


def handle_invalid_data(url, err=None):
    _LOGGER.error(f"Invalid and/or no data received from {url}")
    raise ValueError(f"Invalid and/or no data received from {url}") from err


def parse_response(response):
    waste_data_raw = []
    waste_date = None
    waste_type = None
    DATE_PATTERN = re.compile(r"^\d{8}")

    for line in response.splitlines():
        field, value = line.split(":", 2)
        field = field.split(";")[0]

        if field == "BEGIN" and value == "VEVENT":
            waste_date = None
            waste_type = None
        elif field == "SUMMARY":
            waste_type = _waste_type_rename(waste_type.strip().lower())
        elif field == "DTSTART":
            if DATE_PATTERN.match(value):
                waste_date = f"{value[:4]}-{value[4:6]}-{value[6:8]}"
            else:
                _LOGGER.debug(f"Unsupported waste_date format: {value}")
        elif field == "END" and value == "VEVENT":
            if waste_date and waste_type:
                waste_data_raw.append({"waste_type": waste_type, "waste_date": waste_date})
            else:
                _LOGGER.debug(
                    f"No waste_date or waste_type extracted from event: waste_date={waste_date}, waste_type={waste_type}"
                )

    return waste_data_raw


if __name__ == "__main__":
    print("Yell something at a mountain!")
