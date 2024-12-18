from ..const.const import _LOGGER, SENSOR_COLLECTORS_BURGERPORTAAL
from ..common.main_functions import _waste_type_rename
from datetime import datetime

import requests
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_waste_data_raw(
    provider,
    postal_code,
    street_number,
    suffix,
):

    apikey = 'AIzaSyA6NkRqJypTfP-cjWzrZNFJzPUbBaGjOdk'
    suffix = suffix.strip().upper()

    if provider not in SENSOR_COLLECTORS_BURGERPORTAAL.keys():
        raise ValueError(f"Invalid provider: {provider}, please verify")

    try:
        raw_response = requests.post(
            f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/signupNewUser?key={apikey}"
        ).json()
        if not raw_response:
            _LOGGER.error('Unable to fetch id and refresh token!')
            return
        refresh_token = raw_response['refreshToken']
        id_token = raw_response['idToken']

    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err

    try:
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        data = {
            'grant_type' : 'refresh_token',
            'refresh_token' : refresh_token
        }

        raw_response = requests.post(
            f"https://securetoken.googleapis.com/v1/token?key={apikey}",
            headers=headers,
            data=data,
        ).json()
        if not raw_response:
            _LOGGER.error('Unable to fetch id token!')
            return
        id_token = raw_response['id_token']

    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err

    try:
        headers = {
            'authorization': id_token
        }

        raw_response = requests.get(
            f"https://europe-west3-burgerportaal-production.cloudfunctions.net/exposed/organisations/{SENSOR_COLLECTORS_BURGERPORTAAL[provider]}/address?zipcode={postal_code}&housenumber={street_number}",
            headers=headers, verify=False
        ).json()
        if not raw_response:
            _LOGGER.error('Unable to fetch refresh token!')
            return
        address_id = raw_response[0]['addressId']
    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err

    headers = {
        'authorization': id_token
    }

    raw_response = requests.get(
        f"https://europe-west3-burgerportaal-production.cloudfunctions.net/exposed/organisations/{SENSOR_COLLECTORS_BURGERPORTAAL[provider]}/address/{address_id}/calendar",
        headers=headers, verify=False
    ).json()

    waste_data_raw_temp = raw_response
    waste_data_raw = []
    for item in waste_data_raw_temp:
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

    return sorted(waste_data_raw, key=lambda d: d['date'])



