from ..const.const import _LOGGER, SENSOR_COLLECTORS_CLEANPROFS
from ..common.main_functions import waste_type_rename
from datetime import datetime
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_waste_data_raw(provider, postal_code, street_number, suffix):
    if provider not in SENSOR_COLLECTORS_CLEANPROFS:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    try:
        url = SENSOR_COLLECTORS_CLEANPROFS[provider].format(
            postal_code,
            street_number,
            suffix,
        )
        raw_response = requests.get(url, timeout=60, verify=False)
        raw_response.raise_for_status()
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

    try:
        for item in response:
            if not item['full_date']:
                continue
            waste_type =waste_type_rename(item['product_name'])
            if not waste_type:
                continue
            waste_data_raw.append({"type": waste_type, "date": item['full_date']})

    except requests.exceptions.RequestException as exc:
        _LOGGER.error('Error occurred while fetching data: %r', exc)
        return False

    return waste_data_raw