from ..const.const import _LOGGER, SENSOR_COLLECTOR_TO_URL, SENSOR_COLLECTORS_AFVALWIJZER
from ..common.main_functions import _waste_type_rename
from datetime import datetime
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_waste_data_raw(provider, postal_code, street_number, suffix):
    validate_provider(provider)

    try:
        url = build_url(provider, postal_code, street_number, suffix)
        raw_response = requests.get(url, timeout=60, verify=False)
    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err

    try:
        response = raw_response.json()

        if not response.get("ophaaldagen"):
            handle_invalid_data(url)
    except KeyError as err:
        raise KeyError(f"Invalid and/or no data received from {url}") from err

    try:
        waste_data_raw = (
            response["ophaaldagen"]["data"] + response["ophaaldagenNext"]["data"]
        )
    except KeyError as err:
        raise KeyError(f"Invalid and/or no data received from {url}") from err

    return waste_data_raw


def validate_provider(provider):
    if provider not in SENSOR_COLLECTORS_AFVALWIJZER:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    if provider == "rova":
        provider = "inzamelkalender.rova"


def build_url(provider, postal_code, street_number, suffix):
    return SENSOR_COLLECTOR_TO_URL["afvalwijzer_data_default"][0].format(
        provider,
        postal_code,
        street_number,
        suffix,
        datetime.now().strftime("%Y-%m-%d"),
    )


def handle_invalid_data(url):
    _LOGGER.error("Address not found or no data available!")
    raise KeyError(f"Invalid and/or no data received from {url}")


if __name__ == "__main__":
    print("Yell something at a mountain!")
