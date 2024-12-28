from ..const.const import _LOGGER, SENSOR_COLLECTORS_KLIKOGROEP
from ..common.main_functions import _waste_type_rename

import requests
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def get_waste_data_raw(provider, username, password):
    """Fetch raw waste collection data from the provider API."""
    try:
        base_url = SENSOR_COLLECTORS_KLIKOGROEP[provider]['url']
        app = SENSOR_COLLECTORS_KLIKOGROEP[provider]['app']

        headers = {
            'Content-Type': 'application/json',
            'Referer': base_url,
        }

        # Login and get token
        token = _login_and_get_token(base_url, headers, provider, username, password, app)

        # Get waste calendar
        waste_data_raw = _fetch_waste_calendar(base_url, headers, token, provider, app)

        # Logout (optional, no error handling required here)
        _logout(base_url, headers, token, provider, app)

        return waste_data_raw
    except KeyError as err:
        raise ValueError(f"Invalid provider configuration: {err}") from err

def _login_and_get_token(base_url, headers, provider, username, password, app):
    """Authenticate and retrieve a session token."""
    login_url = f"{base_url}/loginWithPassword"
    data = {
        "cardNumber": username,
        "password": password,
        "clientName": provider,
        "app": app,
    }
    try:
        response = requests.post(url=login_url, timeout=60, headers=headers, json=data)
        response.raise_for_status()
        response_data = response.json()
        if not response_data.get('success'):
            raise ValueError('Login failed. Check username and/or password!')
        return response_data["token"]
    except requests.exceptions.RequestException as err:
        raise ValueError(f"Login request failed: {err}") from err
    except ValueError as err:
        raise ValueError(f"Invalid response from {login_url}: {err}") from err

def _fetch_waste_calendar(base_url, headers, token, provider, app):
    """Retrieve the waste collection calendar."""
    calendar_url = f"{base_url}/getMyWasteCalendar"
    data = {
        "token": token,
        "clientName": provider,
        "app": app,
    }
    try:
        response = requests.post(url=calendar_url, timeout=60, headers=headers, json=data)
        response.raise_for_status()
        response_data = response.json()
    except requests.exceptions.RequestException as err:
        raise ValueError(f"Waste calendar request failed: {err}") from err
    except ValueError as err:
        raise ValueError(f"Invalid response from {calendar_url}: {err}") from err

    return _parse_waste_calendar(response_data)

def _parse_waste_calendar(response):
    """Parse the waste calendar response into a structured list."""
    waste_type_mapping = {
        fraction['id']: _waste_type_rename(fraction['name'].lower())
        for fraction in response.get('fractions', [])
    }

    waste_data_raw = []
    for pickup_date, pickups in response.get("dates", {}).items():
        for pick_up in pickups[0]:
            if pick_up:
                waste_data_raw.append({
                    "type": waste_type_mapping.get(pick_up, "unknown"),
                    "date": pickup_date,
                })

    return waste_data_raw

def _logout(base_url, headers, token, provider, app):
    """Log out to invalidate the session token."""
    logout_url = f"{base_url}/logout"
    data = {
        "token": token,
        "clientName": provider,
        "app": app,
    }
    try:
        requests.post(url=logout_url, timeout=60, headers=headers, json=data)
    except requests.exceptions.RequestException:
        # Logout failures are non-critical, so we can safely ignore them.
        pass
