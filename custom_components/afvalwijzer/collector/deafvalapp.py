from ..const.const import _LOGGER, SENSOR_COLLECTORS_DEAFVALAPP
from ..common.main_functions import _waste_type_rename
from datetime import datetime
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_waste_data_raw(provider, postal_code, street_number, suffix):
    if provider not in SENSOR_COLLECTORS_DEAFVALAPP:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    try:
        url = SENSOR_COLLECTORS_DEAFVALAPP[provider].format(
            postal_code,
            street_number,
            suffix,
        )
        raw_response = requests.get(url, timeout=60, verify=False)
        raw_response.raise_for_status()  # Raise an HTTPError for bad responses
    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err

    try:
        response = raw_response.text
    except ValueError as err:
        raise ValueError(f"Invalid and/or no data received from {url}") from err

    if not response:
        _LOGGER.error("No waste data found!")
        return []

    waste_data_raw = []

    for rows in response.strip().split("\n"):
        for date in rows.split(";")[1:-1]:
            waste_type = _waste_type_rename(rows.split(";")[0].strip().lower())
            waste_date = datetime.strptime(date, "%d-%m-%Y").strftime("%Y-%m-%d")
            waste_data_raw.append({"type": waste_type, "date": waste_date})

    return waste_data_raw



