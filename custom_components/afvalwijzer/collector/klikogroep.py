from ..const.const import _LOGGER, SENSOR_COLLECTORS_KLIKOGROEP
from ..common.main_functions import waste_type_rename
from datetime import datetime
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


def get_waste_data_raw(provider, postal_code, street_number, suffix):
    if provider not in SENSOR_COLLECTORS_KLIKOGROEP.keys():
        raise ValueError(f"Invalid provider: {provider}, please verify")

    try:
        provider_config = SENSOR_COLLECTORS_KLIKOGROEP[provider]
        provider_id = provider_config['id']
        provider_base_url = provider_config['url']

        provider_path = f'/MyKliko/wasteCalendarJSON/{provider_id}/{postal_code}/{street_number}'
        url = f'https://{provider_base_url}{provider_path}'

        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'homeassistant-afvalwijzer',
        }

        raw_response = requests.get(url, headers=headers, timeout=60, verify=False)
        raw_response.raise_for_status()  # Raise an HTTPError for bad responses
    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err

    try:
        response = raw_response.json()
    except ValueError as err:
        raise ValueError(f"Invalid and/or no data received from {url}") from err

    if not response:
        _LOGGER.error("No waste data found!")
        return []

    waste_data_raw = []

    calendar = response.get("calendar", {})

    for date_str, waste_types in calendar.items():
        for waste_code in waste_types.keys():
            waste_type = waste_type_rename(waste_code.strip().lower())
            waste_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
            waste_data_raw.append(
                {
                    "type": waste_type,
                    "date": waste_date,
                }
            )

    return waste_data_raw
