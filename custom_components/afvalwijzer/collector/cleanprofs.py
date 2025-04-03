from ..const.const import _LOGGER, SENSOR_COLLECTORS_CLEANPROFS
from ..common.main_functions import _secondary_type_rename
from datetime import datetime
from homeassistant.helpers.storage import STORAGE_DIR
import requests, json
import os
import glob
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Generate timestamp
timestamp = datetime.now().strftime("%d-%m-%Y_%H_%M_%S")

# Define the backup file name pattern for 'cleanprofs' backups
BACKUP_FILE_PATTERN = os.path.join(STORAGE_DIR, "cleanprofs*.json")

def get_waste_data_raw(provider, postal_code, street_number, suffix):
    if provider not in SENSOR_COLLECTORS_CLEANPROFS:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    # Initialize response variable
    response = None

    try:
        url = SENSOR_COLLECTORS_CLEANPROFS[provider].format(
            postal_code,
            street_number,
            suffix,
        )
        raw_response = requests.get(url, timeout=60, verify=False)

        # If response is not successful (status code not in 200-299), raise an error
        if not raw_response.ok:
            raise ValueError(f"Endpoint {url} returned status {raw_response.status_code}")

        try:
            response = raw_response.json()
        except ValueError as err:
            raise ValueError(f"Invalid and/or no JSON data received from {url}") from err

        # If the API response is OK, delete old backup files and create a new one
        existing_backups = glob.glob(BACKUP_FILE_PATTERN)
        if existing_backups:
            for backup in existing_backups:
                os.remove(backup)
                _LOGGER.debug(f"Deleted old backup file: {backup}")

        # Generate the backup file name with the current timestamp
        BACKUP_FILE = os.path.join(STORAGE_DIR, f"cleanprofs_{timestamp}.json")
        with open(BACKUP_FILE, "w") as backup_file:
            json.dump(response, backup_file)
            _LOGGER.debug(f"CleanProfs backup file created at {BACKUP_FILE}")

    except (requests.exceptions.RequestException, ValueError) as err:
        _LOGGER.error(f"Error fetching data from API: {err}. Loading backup data...")
        # If the API request failed, use the most recent backup instead of creating a new one
        try:
            # Get the most recent backup file based on the pattern
            existing_backups = sorted(glob.glob(BACKUP_FILE_PATTERN), key=os.path.getmtime, reverse=True)
            if existing_backups:
                with open(existing_backups[0], "r", encoding="utf-8") as f:
                    response = json.load(f)
                    _LOGGER.debug(f"Loaded backup file from {existing_backups[0]}")
            else:
                raise ValueError("No backup files found.")
        except (FileNotFoundError, json.JSONDecodeError) as backup_err:
            raise ValueError(f"Failed to load from local json file: {backup_err}")

    if not response:
        _LOGGER.error("No waste data found!")
        return []

    waste_data_raw = []

    try:
        for item in response:
            if not item['full_date']:
                continue
            waste_type = _secondary_type_rename(item['product_name'].strip().lower())
            if not waste_type:
                continue
            waste_data_raw.append({"type": waste_type, "date": item['full_date']})

    except requests.exceptions.RequestException as exc:
        _LOGGER.error('Error occurred while fetching data: %r', exc)
        return False

    return waste_data_raw