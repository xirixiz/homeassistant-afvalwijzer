from ..const.const import _LOGGER, SENSOR_COLLECTOR_TO_URL, SENSOR_COLLECTORS_XIMMIO
from ..common.main_functions import _waste_type_rename
from datetime import datetime, timedelta

import requests
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_waste_data_raw(provider, postal_code, street_number, suffix):
    if provider not in SENSOR_COLLECTORS_XIMMIO:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    collectors = ("avalex", "meerlanden", "rad", "westland")
    provider_url = "ximmio02" if provider in collectors else "ximmio01"

    TODAY = datetime.now().strftime("%d-%m-%Y")
    DATE_TODAY = datetime.strptime(TODAY, "%d-%m-%Y")
    DATE_TOMORROW = DATE_TODAY + timedelta(days=1)
    DATE_TODAY_NEXT_YEAR = (DATE_TODAY.date() + timedelta(days=365)).strftime("%Y-%m-%d")

    ##########################################################################
    # First request: get uniqueId and community
    ##########################################################################
    try:
        url = SENSOR_COLLECTOR_TO_URL[provider_url][0]
        data = {
            "postCode": postal_code,
            "houseNumber": street_number,
            "companyCode": SENSOR_COLLECTORS_XIMMIO[provider],
        }
        raw_response = requests.post(url=url, timeout=60, data=data)
        raw_response.raise_for_status()  # Raise an HTTPError for bad responses
        unique_id = raw_response.json()["dataList"][0]["UniqueId"]
        community = raw_response.json()["dataList"][0]["Community"]
    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err
    except KeyError as err:
        raise KeyError(f"Invalid and/or no data received from {url}") from err

    ##########################################################################
    # Second request: get the dates
    ##########################################################################
    try:
        url = SENSOR_COLLECTOR_TO_URL[provider_url][1]
        data = {
            "companyCode": SENSOR_COLLECTORS_XIMMIO[provider],
            "startDate": DATE_TODAY.date(),
            "endDate": DATE_TODAY_NEXT_YEAR,
            "community": community,
            "uniqueAddressID": unique_id,
        }
        raw_response = requests.post(url=url, timeout=60, data=data)
        raw_response.raise_for_status()  # Raise an HTTPError for bad responses
        response = raw_response.json().get("dataList", [])
    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err
    except KeyError as err:
        raise KeyError(f"Invalid and/or no data received from {url}") from err

    if not response:
        _LOGGER.error("Address not found!")
        return

    return [
        {
            "type": _waste_type_rename(
                item["_pickupTypeText"].strip().lower()
            ),
            "date": datetime.strptime(
                sorted(item["pickupDates"])[0], "%Y-%m-%dT%H:%M:%S"
            ).strftime("%Y-%m-%d"),
        }
        for item in response
    ]


if __name__ == "__main__":
    print("Yell something at a mountain!")
