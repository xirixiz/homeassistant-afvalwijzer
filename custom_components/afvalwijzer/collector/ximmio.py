from datetime import datetime, timedelta

import requests

from ..common.main_functions import _waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTOR_TO_URL, SENSOR_COLLECTORS_XIMMIO


def get_waste_data_raw(
    provider,
    postal_code,
    street_number,
    suffix,
):
    if provider not in SENSOR_COLLECTORS_XIMMIO.keys():
        raise ValueError(f"Invalid provider: {provider}, please verify")

    collectors = ("avalex", "meerlanden", "rad", "westland")
    provider_url = "ximmio02" if provider in collectors else "ximmio01"

    TODAY = datetime.now().strftime("%d-%m-%Y")
    DATE_TODAY = datetime.strptime(TODAY, "%d-%m-%Y")
    DATE_TOMORROW = datetime.strptime(TODAY, "%d-%m-%Y") + timedelta(days=1)
    DATE_TODAY_NEXT_YEAR = (DATE_TODAY.date() + timedelta(days=365)).strftime(
        "%Y-%m-%d"
    )

    ##########################################################################
    # First request: get uniqueId and community
    ##########################################################################
    try:
        url = SENSOR_COLLECTOR_TO_URL[provider_url][0]
        companyCode = SENSOR_COLLECTORS_XIMMIO[provider]
        data = {
            "postCode": postal_code,
            "houseNumber": street_number,
            "companyCode": companyCode,
        }
        raw_response = requests.post(url=url, data=data)
        uniqueId = raw_response.json()["dataList"][0]["UniqueId"]
        community = raw_response.json()["dataList"][0]["Community"]
    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err

    ##########################################################################
    # Second request: get the dates
    ##########################################################################
    try:
        url = SENSOR_COLLECTOR_TO_URL[provider_url][1]
        data = {
            "companyCode": companyCode,
            "startDate": DATE_TODAY.date(),
            "endDate": DATE_TODAY_NEXT_YEAR,
            "community": community,
            "uniqueAddressID": uniqueId,
        }
        raw_response = requests.post(url=url, data=data).json()
    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err

    if not raw_response:
        _LOGGER.error("Address not found!")
        return

    try:
        response = raw_response["dataList"]
    except KeyError as e:
        raise KeyError(f"Invalid and/or no data received from {url}") from e

    waste_data_raw = []

    for item in response:
        temp = {"type": _waste_type_rename(item["_pickupTypeText"].strip().lower())}
        temp["date"] = datetime.strptime(
            sorted(item["pickupDates"])[0], "%Y-%m-%dT%H:%M:%S"
        ).strftime("%Y-%m-%d")
        waste_data_raw.append(temp)

    return waste_data_raw


if __name__ == "__main__":
    print("Yell something at a mountain!")
