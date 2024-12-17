from ..const.const import _LOGGER, SENSOR_COLLECTORS_RWM
from ..common.main_functions import _waste_type_rename
from datetime import datetime
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_waste_data_raw(provider, postal_code, street_number, suffix):
    try:
        if provider != "rwm":
            raise ValueError(f"Invalid provider: {provider}, please verify")

        ##########################################################################
        # First request: get bag id
        ##########################################################################
        url = SENSOR_COLLECTORS_RWM["getAddress"].format(postal_code, street_number)

        response = requests.get(url=url, timeout=60).json()

        if not response:
            _LOGGER.error("Address not found!")
            return []

        bagId = response[0]["bagid"]

        ##########################################################################
        # Second request: get the dates
        ##########################################################################
        url = SENSOR_COLLECTORS_RWM["getSchedule"].format(bagId)

        response = requests.get(url=url, timeout=60).json()

        if not response:
            _LOGGER.error("Could not retrieve trash schedule!")
            return []

        waste_data_raw = []

        for item in response:
            if item["ophaaldatum"] is not None:
                data = {
                    "type": _waste_type_rename(item["title"].strip().lower()),
                    "date": datetime.strptime(item["ophaaldatum"], "%Y-%m-%d").strftime("%Y-%m-%d"),
                }
                waste_data_raw.append(data)

    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err

    return waste_data_raw


if __name__ == "__main__":
    print("Yell something at a mountain!")
