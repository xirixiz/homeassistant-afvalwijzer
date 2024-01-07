from ..const.const import _LOGGER, SENSOR_COLLECTORS_CIRCULUS
from ..common.main_functions import _waste_type_rename
from datetime import datetime, timedelta
import re

import requests
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_waste_data_raw(provider, postal_code, street_number, suffix):
    try:
        suffix = suffix.strip().upper()

        url = SENSOR_COLLECTORS_CIRCULUS[provider]

        raw_response = requests.get(url, timeout=60, verify=False)
        cookies = raw_response.cookies
        session_cookie = ""
        logged_in_cookies = ""
        for item in cookies.items():
            if item[0] == "CB_SESSION":
                session_cookie = item[1]

        raw_response.raise_for_status()  # Raise an HTTPError for bad responses

        if session_cookie:
            authenticityToken = re.search('__AT=(.*)&___TS=', session_cookie)[
                1
            ]
            data = {
                'authenticityToken': authenticityToken,
                'zipCode': postal_code,
                'number': street_number,
            }

            raw_response = requests.post(
                f'{url}/register/zipcode.json', data=data, cookies=cookies
            )

            response = raw_response.json()
            if not response:
                _LOGGER.error("No waste data found!")
                return

            if response["flashMessage"]:
                addresses = response["customData"]["addresses"]
                authenticationUrl = ""
                if suffix:
                    search_pattern = f' {street_number} {suffix.lower()}'
                    for address in addresses:
                        if re.search(search_pattern, address["address"]):
                            authenticationUrl = address["authenticationUrl"]
                            break
                else:
                    authenticationUrl = addresses[0]["authenticationUrl"]
                if authenticationUrl:
                    response = requests.get(
                        url + authenticationUrl, cookies=cookies)

            logged_in_cookies = raw_response.cookies

        else:
            _LOGGER.error("Unable to get Session Cookie")

        if logged_in_cookies:
            startDate = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
            endDate = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")

            headers = {
                'Content-Type': 'application/json'
            }

            response = requests.get(
                f'{url}/afvalkalender.json?from={startDate}&till={endDate}',
                headers=headers,
                cookies=logged_in_cookies,
            ).json()
            if not response or 'customData' not in response or not response['customData']['response']['garbage']:
                _LOGGER.error('No Waste data found!')
                return

            waste_data_raw_temp = response['customData']['response']['garbage']
        else:
            _LOGGER.error("Unable to get Logged-in Cookie")

        waste_data_raw = []
        for item in waste_data_raw_temp:
            for date in item['dates']:
                waste_type = _waste_type_rename(item["code"].strip().lower())
                if not waste_type:
                    continue
                temp = {"type": waste_type, "date": date}
                # temp = datetime.strptime(sorted(item["pickupDates"])[0], "%Y-%m-%dT%H:%M:%S").strftime("%Y-%m-%d")
                waste_data_raw.append(temp)

    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err
    except ValueError as err:
        raise ValueError(f"Invalid and/or no data received from {url}") from err
    return waste_data_raw


if __name__ == "__main__":
    print("Yell something at a mountain!")
