from ..const.const import _LOGGER, SENSOR_COLLECTORS_REINIS
from ..common.main_functions import waste_type_rename, format_postal_code
from datetime import datetime, timedelta
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_waste_data_raw(provider, postal_code, street_number, suffix=""):
    if provider not in SENSOR_COLLECTORS_REINIS:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    try:
        corrected_postal_code = format_postal_code(postal_code)
        url = SENSOR_COLLECTORS_REINIS[provider]

        address_url = f"{url}/adressen/{corrected_postal_code}:{street_number}{suffix}"
        response = requests.get(address_url, timeout=60, verify=False)
        response.raise_for_status()
        address_data = response.json()

        if not address_data or 'bagid' not in address_data[0]:
            _LOGGER.error("No address found, missing bagid!")
            return []

        bagid = address_data[0]['bagid']

    except requests.exceptions.RequestException as err:
        raise ValueError(f"Error fetching address data: {err}") from err

    waste_data_raw = []

    try:
        now = datetime.now()

        kalender_url = f"{url}/rest/adressen/{bagid}/kalender/{now.year}"
        afvalstromen_url = f"{url}/rest/adressen/{bagid}/afvalstromen"

        waste_response = requests.get(kalender_url, timeout=60, verify=False).json()
        afvalstroom_response = requests.get(afvalstromen_url, timeout=60, verify=False).json()

        for item in waste_response:
            if not item.get('ophaaldatum') or not item.get('afvalstroom_id'):
                continue

            afval_type = next(
                (waste_type_rename(a['title']) for a in afvalstroom_response if a['id'] == item['afvalstroom_id']),
                None
            )
            if not afval_type:
                continue

            waste_data_raw.append({"type": afval_type, "date": item['ophaaldatum']})

    except requests.exceptions.RequestException as exc:
        _LOGGER.error('Error occurred while fetching waste data: %r', exc)
        return []

    return waste_data_raw