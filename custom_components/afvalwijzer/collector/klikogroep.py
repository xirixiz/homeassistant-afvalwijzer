from ..const.const import _LOGGER, SENSOR_COLLECTORS_KLIKOGROEP
from ..common.main_functions import _waste_type_rename
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_waste_data_raw(provider, postal_code, street_number, suffix, username, password):
    try:
        url = SENSOR_COLLECTORS_KLIKOGROEP[provider]['url']
        app = SENSOR_COLLECTORS_KLIKOGROEP[provider]['app']

        headers = {
            'Content-Type': 'application/json',
            'Referer': url,
        }

        ##########################################################################
        # First request: login and get token
        ##########################################################################
        data = {
            "cardNumber": username,
            "password": password,
            "clientName": provider,
            "app": app,
        }

        try:
            raw_response = requests.post(url="{}/loginWithPassword".format(url), timeout=60, headers=headers, json=data)
            raw_response.raise_for_status() 
        except requests.exceptions.RequestException as err:
            raise ValueError(err) from err
        
        try:
            response = raw_response.json()
        except ValueError as err:
            raise ValueError(f"Invalid and/or no data received from {url}") from err

        if 'success' not in response or not response['success']:
            _LOGGER.error('Login failed. Check card number (username) and / or password!')
            return

        token = response["token"]

        ##########################################################################
        # Second request: get the dates
        ##########################################################################
        data = {
            "token": token,
            "clientName": provider,
            "app": app,
        }

        response = requests.post(url="{}/getMyWasteCalendar".format(url), timeout=60, headers=headers, json=data).json()

        if not response:
            _LOGGER.error("Fetching WasteCalendar failed!")
            return []

        waste_data_raw = []
        waste_type_mapping = {}
        for waste_type in response['fractions']:
            waste_type_mapping[waste_type['id']] = _waste_type_rename(waste_type['name'].lower())

        for pickup_date in response["dates"]:
            num_pickup = len(response["dates"][pickup_date][0])
            for idx in range(0, num_pickup):
                pick_up = response["dates"][pickup_date][0][idx]
                if pick_up != 0:
                    waste_data_raw.append({
                        "type": waste_type_mapping[pick_up],
                        "date": pickup_date,
                    })

        ##########################################################################
        # Third request: invalidate token / close session
        ##########################################################################
        data = {
            "token": token,
            "clientName": provider,
            "app": app,
        }

        response = requests.post(url="{}/logout".format(url), timeout=60, headers=headers, json=data).json()
        # We really don't care about the result, honestly.

    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err

    return waste_data_raw
