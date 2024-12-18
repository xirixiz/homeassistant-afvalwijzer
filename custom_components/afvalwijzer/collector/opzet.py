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
        _verify = provider != "suez"
        url_address = f"{SENSOR_COLLECTORS_OPZET[provider]}/rest/adressen/{postal_code}-{street_number}"
        raw_response_address = requests.get(url_address, timeout=60, verify=False)
        raw_response_address.raise_for_status()  # Raise an HTTPError for bad responses

        response_address = raw_response_address.json()

        if not response_address:
            _LOGGER.error("No waste data found!")
            return []

        bag_id = None

        if len(response_address) > 1 and suffix:
            for item in response_address:
                if item["huisletter"] == suffix or item["huisnummerToevoeging"] == suffix:
                    bag_id = item["bagId"]
                    break
        else:
            bag_id = response_address[0]["bagId"]

        url_waste = f"{SENSOR_COLLECTORS_OPZET[provider]}/rest/adressen/{bag_id}/afvalstromen"
        raw_response_waste = requests.get(url_waste, timeout=60, verify=False)
        raw_response_waste.raise_for_status()  # Raise an HTTPError for bad responses

        waste_data_raw_temp = raw_response_waste.json()
        waste_data_raw = []

        for item in waste_data_raw_temp:
            if not item["ophaaldatum"]:
                continue

            waste_type = _waste_type_rename(item["menu_title"].strip().lower())
            if not waste_type:
                continue

            waste_date = datetime.strptime(item["ophaaldatum"], "%Y-%m-%d").strftime("%Y-%m-%d")
            waste_data_raw.append({"type": waste_type, "date": waste_date})

    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err

    return waste_data_raw



