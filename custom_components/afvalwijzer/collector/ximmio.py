from ..const.const import _LOGGER, SENSOR_COLLECTORS_XIMMIO, SENSOR_COLLECTORS_XIMMIO_IDS
from ..common.main_functions import waste_type_rename
from datetime import datetime, timedelta
import requests
from urllib3.exceptions import InsecureRequestWarning

import socket
from urllib3.util import connection as urllib3_connection

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def _post_ipv4_then_ipv6(url: str, **kwargs) -> requests.Response:
    """Try POST via IPv4 first; if that fails (DNS/connect), try IPv6."""
    original_allowed = urllib3_connection.allowed_gai_family

    try:
        urllib3_connection.allowed_gai_family = lambda: socket.AF_INET
        return requests.post(url=url, **kwargs)
    except requests.exceptions.RequestException as e_v4:
        last_err = e_v4
    finally:
        urllib3_connection.allowed_gai_family = original_allowed

    try:
        urllib3_connection.allowed_gai_family = lambda: socket.AF_INET6
        return requests.post(url=url, **kwargs)
    except requests.exceptions.RequestException as e_v6:
        raise ValueError(f"POST failed (IPv4 then IPv6): {last_err}") from e_v6
    finally:
        urllib3_connection.allowed_gai_family = original_allowed

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

        response = _post_ipv4_then_ipv6(url=f"{url}/api/FetchAdress", timeout=60, data=data).json()

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

        response = _post_ipv4_then_ipv6(url=f"{url}/api/GetCalendar", timeout=60, data=data).json()

        if not response:
            _LOGGER.error("Address not found!")
            return []

        waste_data_raw = []

        for item in response["dataList"]:
            if pickup_dates := sorted(item.get("pickupDates", [])):
                temp = {
                    "type": waste_type_rename(item["_pickupTypeText"].strip().lower()),
                    "date": datetime.strptime(pickup_dates[0], "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d"),
                }
                waste_data_raw.append(temp)

    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err

    return waste_data_raw



