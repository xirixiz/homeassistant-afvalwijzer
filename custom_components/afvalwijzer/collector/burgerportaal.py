from ..const.const import _LOGGER, SENSOR_COLLECTORS_BURGERPORTAAL
from ..common.main_functions import _waste_type_rename
from datetime import datetime

import requests
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

API_KEY = 'AIzaSyA6NkRqJypTfP-cjWzrZNFJzPUbBaGjOdk'


def get_waste_data_raw(provider, postal_code, street_number, suffix):
    suffix = suffix.strip().upper()

    validate_provider(provider)

    id_token, refresh_token = get_tokens()

    headers = {'authorization': id_token}

    address_id = get_address_id(provider, postal_code, street_number, headers)

    raw_response = get_calendar_data(provider, address_id, headers)

    waste_data_raw = parse_response(raw_response)

    return sorted(waste_data_raw, key=lambda d: d['date'])


def validate_provider(provider):
    if provider not in SENSOR_COLLECTORS_BURGERPORTAAL.keys():
        raise ValueError(f"Invalid provider: {provider}, please verify")


def get_tokens():
    try:
        refresh_token = get_refresh_token()
        id_token = refresh_to_id_token(refresh_token)
        return id_token, refresh_token
    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err


def get_refresh_token():
    try:
        raw_response = requests.post(
            f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/signupNewUser?key={API_KEY}"
        ).json()
        if not raw_response:
            _LOGGER.error('Unable to fetch id and refresh token!')
            return
        return raw_response['refreshToken']
    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err


def refresh_to_id_token(refresh_token):
    try:
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        data = {'grant_type': 'refresh_token', 'refresh_token': refresh_token}
        raw_response = requests.post(
            f"https://securetoken.googleapis.com/v1/token?key={API_KEY}",
            headers=headers,
            data=data,
        ).json()
        if not raw_response:
            _LOGGER.error('Unable to fetch id token!')
            return
        return raw_response['id_token']
    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err


def get_address_id(provider, postal_code, street_number, headers):
    try:
        raw_response = requests.get(
            f"https://europe-west3-burgerportaal-production.cloudfunctions.net/exposed/organisations/{SENSOR_COLLECTORS_BURGERPORTAAL[provider]}/address?zipcode={postal_code}&housenumber={street_number}",
            headers=headers,
            verify=False
        ).json()
        if not raw_response:
            _LOGGER.error('Unable to fetch address id!')
            return
        return raw_response[0]['addressId']
    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err


def get_calendar_data(provider, address_id, headers):
    try:
        return requests.get(
            f"https://europe-west3-burgerportaal-production.cloudfunctions.net/exposed/organisations/{SENSOR_COLLECTORS_BURGERPORTAAL[provider]}/address/{address_id}/calendar",
            headers=headers,
            verify=False,
        ).json()
    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err


def parse_response(raw_response):
    waste_data_raw = []
    for item in raw_response:
        if not item["collectionDate"]:
            continue
        waste_type = item["fraction"]
        if not waste_type:
            continue

        temp = {"type": _waste_type_rename(item["fraction"].strip().lower())}
        temp_date = item["collectionDate"][:item["collectionDate"].rfind("T")]
        temp["date"] = datetime.strptime(temp_date, "%Y-%m-%d").strftime(
            "%Y-%m-%d"
        )
        waste_data_raw.append(temp)

    return waste_data_raw


if __name__ == "__main__":
    print("Yell something at a mountain!")
