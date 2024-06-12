from ..const.const import _LOGGER, SENSOR_COLLECTOR_TO_URL, SENSOR_COLLECTORS_XIMMIO
from ..common.main_functions import _waste_type_rename
from datetime import datetime, timedelta
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_waste_data_raw(provider, postal_code, street_number, suffix):
    try:
        if provider not in SENSOR_COLLECTORS_XIMMIO:
            raise ValueError(f"Invalid provider: {provider}, please verify")

        collectors = ("avalex", "meerlanden", "rad", "westland", "woerden")
        provider_url = "ximmio02" if provider in collectors else "ximmio01"

        TODAY = datetime.now().strftime("%d-%m-%Y")
        DATE_TODAY = datetime.strptime(TODAY, "%d-%m-%Y")
        DATE_TODAY_NEXT_YEAR = (DATE_TODAY.date() + timedelta(days=365)).strftime("%Y-%m-%d")

        ##########################################################################
        # First request: get uniqueId and community
        ##########################################################################
        url = SENSOR_COLLECTOR_TO_URL[provider_url][0]
        data = {
            "postCode": postal_code,
            "houseNumber": street_number,
            "companyCode": SENSOR_COLLECTORS_XIMMIO[provider],
        }

        if suffix:
            data["HouseLetter"] = suffix

        response = requests.post(url=url, timeout=60, data=data).json()
        uniqueId = response["dataList"][0]["UniqueId"]
        community = response["dataList"][0]["Community"]

        ##########################################################################
        # Second request: get the dates
        ##########################################################################
        url = SENSOR_COLLECTOR_TO_URL[provider_url][1]
        data = {
            "companyCode": SENSOR_COLLECTORS_XIMMIO[provider],
            "startDate": DATE_TODAY.date(),
            "endDate": DATE_TODAY_NEXT_YEAR,
            "community": community,
            "uniqueAddressID": uniqueId,
        }

        response = requests.post(url=url, timeout=60, data=data).json()

        if not response:
            _LOGGER.error("Address not found!")
            return []

        waste_data_raw = []

        for item in response["dataList"]:
            if pickup_dates := sorted(item.get("pickupDates", [])):
                temp = {
                    "type": _waste_type_rename(item["_pickupTypeText"].strip().lower()),
                    "date": datetime.strptime(pickup_dates[0], "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d"),
                }
                waste_data_raw.append(temp)

    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err

    return waste_data_raw


if __name__ == "__main__":
    print("Yell something at a mountain!")
