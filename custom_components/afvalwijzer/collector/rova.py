from ..const.const import _LOGGER, SENSOR_COLLECTORS_ROVA
from ..common.main_functions import _waste_type_rename
from datetime import datetime
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_waste_data_raw(provider, postal_code, street_number, suffix):
    try:
        suffix = suffix.strip().upper()

        url = SENSOR_COLLECTORS_ROVA.get(provider)

        if not url:
            raise ValueError(f"Invalid provider: {provider}, please verify")

        raw_response = requests.get(
            '{}/api/waste-calendar/upcoming?houseNumber={}&addition={}&postalcode={}&take=10'.format(url, street_number, suffix, postal_code, timeout=60, verify=False)
        )
        raw_response.raise_for_status()  # Raise an HTTPError for bad responses
    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err

    try:
        response = raw_response.json()
    except ValueError as err:
        raise ValueError(f"Invalid and/or no data received from {url}") from err

    if not response:
        _LOGGER.error("No waste data found!")
        return []

    waste_data_raw = []

    for item in response:
        waste_type = _waste_type_rename(item["wasteType"]["title"])
        waste_date = datetime.strptime(item['date'], "%Y-%m-%dT%H:%M:%SZ").strftime("%Y-%m-%d")
        waste_data_raw.append({"type": waste_type, "date": waste_date})

        if not waste_type or not waste_date:
            continue

    return waste_data_raw
