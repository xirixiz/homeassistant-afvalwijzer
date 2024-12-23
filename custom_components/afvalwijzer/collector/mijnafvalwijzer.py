from ..const.const import _LOGGER, SENSOR_COLLECTOR_TO_URL, SENSOR_COLLECTORS_AFVALWIJZER
from datetime import datetime
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_waste_data_raw(provider, postal_code, street_number, suffix):
    if provider not in SENSOR_COLLECTORS_AFVALWIJZER:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    try:
        url = SENSOR_COLLECTOR_TO_URL["afvalwijzer_data_default"][0].format(
            provider,
            postal_code,
            street_number,
            suffix,
            datetime.now().strftime("%Y-%m-%d"),
        )
        raw_response = requests.get(url, timeout=60, verify=False)
        raw_response.raise_for_status()  # Raise an HTTPError for bad responses
    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err

    try:
        response = raw_response.json()
        ophaaldagen_data = response.get("ophaaldagen", {}).get("data", [])
        ophaaldagen_next_data = response.get("ophaaldagenNext", {}).get("data", [])

        if not ophaaldagen_data and not ophaaldagen_next_data:
            _LOGGER.error("Address not found or no data available!")
            raise KeyError
    except KeyError as err:
        raise KeyError(f"Invalid and/or no data received from {url}") from err

    return ophaaldagen_data + ophaaldagen_next_data[:25]
