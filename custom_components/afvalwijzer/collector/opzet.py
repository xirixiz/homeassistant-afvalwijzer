from ..const.const import _LOGGER, SENSOR_COLLECTORS_OPZET
from ..common.main_functions import _waste_type_rename
from datetime import datetime

import requests
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_waste_data_raw(provider, postal_code, street_number, suffix):
    if provider not in SENSOR_COLLECTORS_OPZET:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    try:
        suffix = suffix.strip().upper()
        verify_ssl = provider != "suez"
        url = f"{SENSOR_COLLECTORS_OPZET[provider]}/rest/adressen/{postal_code}-{street_number}"
        raw_response = requests.get(url, timeout=60, verify=verify_ssl)
        raw_response.raise_for_status()  # Raise an HTTPError for bad responses
        response = raw_response.json()

        if not response:
            _LOGGER.error("No waste data found!")
            return

        bag_id = (
            next(
                (
                    item["bagId"]
                    for item in response
                    if item["huisletter"] == suffix
                    or item["huisnummerToevoeging"] == suffix
                ),
                response[0]["bagId"] if response else None,
            )
        )

        url = f"{SENSOR_COLLECTORS_OPZET[provider]}/rest/adressen/{bag_id}/afvalstromen"
        waste_data_raw_temp = requests.get(url, timeout=60, verify=verify_ssl).json()
        waste_data_raw = []

        for item in waste_data_raw_temp:
            if not item["ophaaldatum"]:
                continue
            waste_type = item["menu_title"]
            if not waste_type:
                continue
            temp = {"type": _waste_type_rename(waste_type.strip().lower())}
            temp["date"] = datetime.strptime(item["ophaaldatum"], "%Y-%m-%d").strftime("%Y-%m-%d")
            waste_data_raw.append(temp)

    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err
    except ValueError as err:
        raise ValueError(f"Invalid and/or no data received from {url}") from err

    return waste_data_raw


if __name__ == "__main__":
    print("Yell something at a mountain!")
