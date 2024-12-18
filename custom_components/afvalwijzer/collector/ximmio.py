from ..const.const import _LOGGER, SENSOR_COLLECTORS_XIMMIO, SENSOR_COLLECTORS_XIMMIO_IDS
from ..common.main_functions import _waste_type_rename
from datetime import datetime, timedelta
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_waste_data_raw(provider, postal_code, street_number, suffix):
    try:
        suffix = suffix.strip().upper()

        if provider not in SENSOR_COLLECTORS_XIMMIO_IDS:
            raise ValueError(f"Invalid provider: {provider} for XIMMIO, please verify")

        if provider in SENSOR_COLLECTORS_XIMMIO.keys():
            url = SENSOR_COLLECTORS_XIMMIO[provider]
        else:
            url = SENSOR_COLLECTORS_XIMMIO["ximmio"]

        if not url:
            raise ValueError(f"Invalid provider: {provider} for XIMMIO, please verify")

        TODAY = datetime.now().strftime("%d-%m-%Y")
        DATE_TODAY = datetime.strptime(TODAY, "%d-%m-%Y")
        DATE_TODAY_NEXT_YEAR = (DATE_TODAY.date() + timedelta(days=365)).strftime("%Y-%m-%d")

        ##########################################################################
        # First request: get uniqueId and community
        ##########################################################################
        data = {
            "postCode": postal_code,
            "houseNumber": street_number,
            "companyCode": SENSOR_COLLECTORS_XIMMIO_IDS[provider],
        }

        if suffix:
            data["HouseLetter"] = suffix
        response = requests.post(url="{}/api/FetchAdress".format(url), timeout=60, data=data).json()

        if not response['dataList']:
            _LOGGER.error('Address not found!')
            return

        uniqueId = response["dataList"][0]["UniqueId"]
        community = response["dataList"][0]["Community"]

        ##########################################################################
        # Second request: get the dates
        ##########################################################################
        data = {
            "companyCode": SENSOR_COLLECTORS_XIMMIO_IDS[provider],
            "startDate": DATE_TODAY.date(),
            "endDate": DATE_TODAY_NEXT_YEAR,
            "community": community,
            "uniqueAddressID": uniqueId,
        }

        response = requests.post(url="{}/api/GetCalendar".format(url), timeout=60, data=data).json()

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



