from ..const.const import _LOGGER, CLEAN_COLLECTORS_CLEANPROFS
from ..common.main_functions import _clean_type_rename, format_postal_code
from datetime import datetime
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def get_waste_data_raw(provider, postal_code, street_number, suffix):
    try:
        if provider not in CLEAN_COLLECTORS_CLEANPROFS:
            raise ValueError(f"Invalid provider: {provider}, please verify")
        
        corrected_postal_code = format_postal_code(postal_code)

        url = CLEAN_COLLECTORS_CLEANPROFS[provider].format(
            corrected_postal_code,
            street_number,
            suffix,
        )
        raw_response = requests.get(url, timeout=60, verify=False)
        raw_response.raise_for_status()

        response = raw_response.json()

        if not response:
            _LOGGER.error("No waste data found!")
            return []
        
        waste_data_raw = []

        for item in response:
            if not item.get("full_date"):
                continue

            waste_type = _clean_type_rename(item["product_name"].strip().lower())

            if not waste_type:
                continue

            waste_data_raw.append({"type": waste_type, "date": item["full_date"]})

    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err
    
    return waste_data_raw