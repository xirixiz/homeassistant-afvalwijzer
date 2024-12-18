from ..const.const import _LOGGER, SENSOR_COLLECTORS_AFVALALERT
from ..common.main_functions import _waste_type_rename
from datetime import datetime
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_waste_data_raw(provider, postal_code, street_number, suffix):
    if provider not in SENSOR_COLLECTORS_AFVALALERT:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    try:
        suffix = "a"
        url = SENSOR_COLLECTORS_AFVALALERT[provider]

        response = requests.get('{}/{}/{}{}'.format(url, postal_code, street_number, suffix), timeout=60, verify=False)
        print(response)
        response.raise_for_status()  # Raise an HTTPError for bad responses
    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err

    if not response:
        _LOGGER.error("No waste data found!")
        return []

    waste_data_raw = []

    try:
        for item in response['items']:
            if not item['date']:
                continue
            waste_type =_waste_type_rename(item['type'])
            if not waste_type:
                continue
            waste_date=datetime.strptime(item['date'], '%Y-%m-%d'),
            waste_data_raw.append({"type": waste_type, "date": waste_date})

    except requests.exceptions.RequestException as exc:
        _LOGGER.error('Error occurred while fetching data: %r', exc)
        return False

    return waste_data_raw



