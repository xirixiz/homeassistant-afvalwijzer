from ..const.const import _LOGGER, SENSOR_COLLECTORS_DEAFVALAPP
from ..common.main_functions import _waste_type_rename
from datetime import datetime
import re
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_waste_data_raw(provider, postal_code, street_number, suffix):
    validate_provider(provider)

    corrected_postal_code = correct_postal_code(postal_code)

    try:
        url = build_url(provider, corrected_postal_code, street_number, suffix)
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
    if provider not in SENSOR_COLLECTORS_DEAFVALAPP.keys():
        raise ValueError(f"Invalid provider: {provider}, please verify")


def correct_postal_code(postal_code):
    corrected_postal_code_parts = re.search(r"(\d\d\d\d) ?([A-z][A-z])", postal_code)
    return corrected_postal_code_parts[1] + corrected_postal_code_parts[2].upper()


def build_url(provider, postal_code, street_number, suffix):
    return SENSOR_COLLECTORS_DEAFVALAPP[provider].format(
        postal_code,
        street_number,
        suffix,
    )


def handle_request_exception(err):
    raise ValueError(err) from err


def handle_invalid_data(url, err=None):
    _LOGGER.error(f"Invalid and/or no data received from {url}")
    raise ValueError(f"Invalid and/or no data received from {url}") from err


def parse_response(response):
    waste_data_raw = []

    for rows in response.strip().split("\n"):
        for ophaaldatum in rows.split(";")[1:-1]:
            temp = {"type": _waste_type_rename(rows.split(";")[0].strip().lower())}
            temp["date"] = datetime.strptime(ophaaldatum, "%d-%m-%Y").strftime(
                "%Y-%m-%d"
            )
            waste_data_raw.append(temp)

    return waste_data_raw


if __name__ == "__main__":
    print("Yell something at a mountain!")
