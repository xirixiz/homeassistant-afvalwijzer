from ..const.const import _LOGGER, SENSOR_COLLECTORS_IRADO
from ..common.main_functions import waste_type_rename, format_postal_code
from datetime import datetime
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def get_waste_data_raw(provider, postal_code, street_number, suffix):
    try:
        if provider not in SENSOR_COLLECTORS_IRADO:
            raise ValueError(f"Invalid provider: {provider}, please verify")

        corrected_postal_code = format_postal_code(postal_code)

        url = SENSOR_COLLECTORS_IRADO[provider].format(
            corrected_postal_code,
            street_number,
            suffix,
        )
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
        raw_response = requests.get(url, headers=headers, timeout=60, verify=False)

        raw_response.raise_for_status()
        response = raw_response.json()

        if not response:
            _LOGGER.error("No waste data found!");
            return []

        if not response["valid"]:
            _LOGGER.error("Äddress not found!")
            return []
        waste_data_raw_temp = response["calendar_data"]["pickups"]
        waste_data_raw = []

        for year, months in waste_data_raw_temp.items():
            for month, days in months.items():
                for day, items in days.items():
                    for item in items:
                        if "date" not in item or not item["date"]: #Check if date exists
                            continue

                        waste_type = waste_type_rename(item["type"].strip().lower())
                        if not waste_type:
                            continue

                        waste_date = datetime.strptime(item["date"], "%d/%m/%Y").strftime("%Y-%m-%d")
                        waste_data_raw.append({"type": waste_type, "date": waste_date})

    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err
    return waste_data_raw