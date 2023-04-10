from ..const.const import _LOGGER, SENSOR_COLLECTORS_RD4
from ..common.main_functions import _waste_type_rename
from datetime import datetime
import re

import requests
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_waste_data_raw(
    provider,
    postal_code,
    street_number,
    suffix,
):
    if provider not in SENSOR_COLLECTORS_RD4.keys():
        raise ValueError(f"Invalid provider: {provider}, please verify")

    TODAY = datetime.now()
    YEAR_CURRENT = TODAY.year

    corrected_postal_code_parts = re.search(r"(\d\d\d\d) ?([A-z][A-z])", postal_code)
    corrected_postal_code = (
        f"{corrected_postal_code_parts[1]}+{corrected_postal_code_parts[2].upper()}"
    )

    try:
        url = SENSOR_COLLECTORS_RD4[provider].format(
            corrected_postal_code,
            street_number,
            suffix,
            YEAR_CURRENT,
        )
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

    if not response["success"]:
        _LOGGER.error("Address not found!")
        return

    try:
        waste_data_raw_temp = response["data"]["items"][0]
    except KeyError as err:
        raise KeyError(f"Invalid and/or no data received from {url}") from err

    waste_data_raw = []

    for item in waste_data_raw_temp:
        if not item["date"]:
            continue

        waste_type = item["type"]
        if not waste_type:
            continue

        temp = {"type": _waste_type_rename(item["type"].strip().lower())}
        temp["date"] = datetime.strptime(item["date"], "%Y-%m-%d").strftime("%Y-%m-%d")
        waste_data_raw.append(temp)

    return waste_data_raw


if __name__ == "__main__":
    print("Yell something at a mountain!")
