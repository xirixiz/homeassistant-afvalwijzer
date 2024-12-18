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

        url = SENSOR_COLLECTORS_CIRCULUS.get(provider)

        if not url:
            raise ValueError(f"Invalid provider: {provider}, please verify")

        response, logged_in_cookies = get_session_cookie(url, postal_code, street_number, suffix)

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
                    url + authenticationUrl, cookies=logged_in_cookies)
        waste_data_raw = get_waste_data(logged_in_cookies, url)
    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err

    return waste_data_raw

def get_session_cookie(url, postal_code, street_number, suffix):
    raw_response = requests.get(url, timeout=60, verify=False)
    raw_response.raise_for_status()  # Raise an HTTPError for bad responses

    cookies = raw_response.cookies
    if session_cookie := cookies.get("CB_SESSION", ""):

        authenticity_token = re.search('__AT=(.*)&___TS=', session_cookie)
        authenticity_token = authenticity_token[1] if authenticity_token else ""
        data = {
            'authenticityToken': authenticity_token,
            'zipCode': postal_code,
            'number': street_number,
        }

        raw_response = requests.post(
            f'{url}/register/zipcode.json', data=data, cookies=cookies
        )
        response = raw_response.json()

        logged_in_cookies = raw_response.cookies

        return response, logged_in_cookies
    else:
        _LOGGER.error("Unable to get Session Cookie")
        return None

def get_waste_data(logged_in_cookies, url):
    if logged_in_cookies:

        start_date = (datetime.now() - timedelta(days=14)).strftime("%Y-%m-%d")
        end_date = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")

        headers = {
            'Content-Type': 'application/json'
        }

        response = requests.get(
            f'{url}/afvalkalender.json?from={start_date}&till={end_date}',
            headers=headers,
            cookies=logged_in_cookies,
        ).json()

        if not response or 'customData' not in response or not response['customData']['response']['garbage']:
            _LOGGER.error('No Waste data found!')
            return []

        waste_data_raw = []
        for item in response['customData']['response']['garbage']:
            for date in item['dates']:
                if waste_type := _waste_type_rename(item["code"].strip().lower()):
                    waste_data_raw.append({"type": waste_type, "date": date})
        return waste_data_raw

    else:
        _LOGGER.error("Unable to get Logged-in Cookie")
        return []



