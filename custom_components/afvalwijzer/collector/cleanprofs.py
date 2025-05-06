from ..const.const import _LOGGER, SENSOR_COLLECTORS_CLEANPROFS
from ..common.main_functions import secondary_type_rename
from datetime import datetime, timedelta
from homeassistant.helpers.storage import STORAGE_DIR
import requests
import json
import os
import glob
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Define the backup file pattern
BACKUP_FILE_PATTERN = os.path.join(STORAGE_DIR, "cleanprofs_*.json")

def get_waste_data_raw(provider, postal_code, street_number, suffix):
    if provider not in SENSOR_COLLECTORS_CLEANPROFS:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    # Initialize response variable
    response = None

    # Get the most recent backup file, if it exists
    existing_backups = sorted(glob.glob(BACKUP_FILE_PATTERN), key=os.path.getmtime, reverse=True)
    latest_backup = existing_backups[0] if existing_backups else None
    backup_age_ok = False
    usable_backup_exists = False

    if latest_backup:
        file_time = datetime.fromtimestamp(os.path.getmtime(latest_backup))
        backup_age_ok = (datetime.now() - file_time) < timedelta(days=1)

        #Ensure backup is usable
        try:
            with open(latest_backup, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if content and content != "[]":
                    usable_backup_exists = True
        except Exception as e:
            _LOGGER.error(f"Failed to read backup file {latest_backup}: {e}")
    else:
        usable_backup_exists = False

    try:
        # API Request
        url = SENSOR_COLLECTORS_CLEANPROFS[provider].format(postal_code, street_number, suffix)
        raw_response = requests.get(url, timeout=60, verify=False)

        if raw_response.ok and raw_response.json() == [] and not usable_backup_exists:
            raise ValueError(f"Endpoint {url} returned an empty array and no usable backup, indicating no data available for {postal_code} {street_number} {suffix}")

        if not raw_response.ok:
            raise ValueError(f"Endpoint {url} returned status {raw_response.status_code}")

        try:
            response = raw_response.json()
        except ValueError as err:
            raise ValueError(f"Invalid and/or no JSON data received from {url}") from err

        # If API response is OK, handle backup creation
        if latest_backup and backup_age_ok:
            _LOGGER.debug(f"Existing backup is recent ({latest_backup}), skipping new backup creation.")
        else:
            timestamp = datetime.now().strftime("%d-%m-%Y_%H_%M_%S")
            new_backup = os.path.join(STORAGE_DIR, f"cleanprofs_{timestamp}.json")

            with open(new_backup, "w") as backup_file:
                json.dump(response, backup_file)
                _LOGGER.debug(f"New backup created: {new_backup}")

            if latest_backup:
                os.remove(latest_backup)
                _LOGGER.debug(f"Deleted old backup file: {latest_backup}")

    except (requests.exceptions.RequestException, ValueError) as err:
        _LOGGER.error(f"Error fetching data from API: {err}. Attempting to use backup...")

        if latest_backup and usable_backup_exists:
            with open(latest_backup, "r", encoding="utf-8") as f:
                response = json.load(f)
                _LOGGER.warning(
                    f"BAD API response, using backup file: {latest_backup} "
                    f"{'(older than 1 day)' if not backup_age_ok else ''}"
                )
        else:
            _LOGGER.error("BAD API response and no local backup file available.")
            return False

    if not response:
        _LOGGER.error("No waste data found for cleanprofs!")
        return False

    waste_data_raw = []
    try:
        for item in response:
            if not item['full_date']:
                continue
            waste_type = secondary_type_rename(item['product_name'].strip().lower())
            if not waste_type:
                continue
            waste_data_raw.append({"type": waste_type, "date": item['full_date']})

    except requests.exceptions.RequestException as exc:
        _LOGGER.error('Error occurred while fetching data: %r', exc)
        return False

    return waste_data_raw