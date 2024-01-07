from ..const.const import _LOGGER, SENSOR_COLLECTOR_TO_URL
from ..common.main_functions import _waste_type_rename
from datetime import datetime

import requests
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_waste_data_raw(
    provider,
    postal_code,
    street_number,
    suffix,
):
    url = f"{SENSOR_COLLECTOR_TO_URL[provider][0]}"

    try:
        raw_response = requests.get(url, timeout=60, verify=False)
    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err

    try:
        response = raw_response.json()
    except ValueError as err:
        raise ValueError(f"Invalid and/or no data received from {url}") from err

    if not response:
        _LOGGER.error("No waste data found!")
        return

    try:
        waste_data_raw_temp = requests.get(url, timeout=60, verify=False).json()
        waste_data_raw = []
        for item in waste_data_raw_temp:
            if not item["ophaaldatum"]:
                continue
            waste_type = item["menu_title"]
            if not waste_type:
                continue
            temp = {"type": _waste_type_rename(item["menu_title"].strip().lower())}
            temp["date"] = datetime.strptime(item["ophaaldatum"], "%Y-%m-%d").strftime(
                "%Y-%m-%d"
            )
            waste_data_raw.append(temp)
    except ValueError as err:
        raise ValueError(f"Invalid and/or no data received from {url}") from err

    return waste_data_raw


if __name__ == "__main__":
    print("Yell something at a mountain!")
