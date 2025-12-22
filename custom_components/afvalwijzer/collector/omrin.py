from __future__ import annotations

from base64 import b64decode, b64encode
from datetime import datetime
import json
import uuid
from typing import Any

import requests
from Cryptodome.PublicKey import RSA
from rsa import pkcs1
from urllib3.exceptions import InsecureRequestWarning

from ..const.const import _LOGGER, SENSOR_COLLECTORS_OMRIN
from ..common.main_functions import waste_type_rename, format_postal_code

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
DEFAULT_TIMEOUT = 60

def _post_json(
    session: requests.Session,
    url: str,
    *,
    json_body: Any | None = None,
    data: Any | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> Any:
    """POST helper with consistent error handling."""
    resp = session.post(url, json=json_body, data=data, timeout=timeout, verify=False)
    try:
        resp.raise_for_status()
    except requests.HTTPError as err:
        raise ValueError(f"HTTP error calling {url}: {resp.status_code}") from err

    try:
        return resp.json()
    except ValueError as err:
        raise ValueError(f"Non-JSON response from {url}") from err


def get_waste_data_raw(provider: str, postal_code: str, street_number: str, suffix: str | None = None) -> list[dict[str, str]]:
    """
    Fetch waste pickup calendar from Omrin-like providers.

    Returns: [{"type": "<waste_type>", "date": "YYYY-MM-DD"}, ...]
    """
    corrected_postal_code = format_postal_code(postal_code)
    if provider not in SENSOR_COLLECTORS_OMRIN:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    base_url = SENSOR_COLLECTORS_OMRIN[provider].rstrip("/")
    app_id = str(uuid.uuid1())

    with requests.Session() as session:
        # Get public key
        _LOGGER.debug("Fetching public key from Omrin provider=%s url=%s", provider, base_url)
        token_url = f"{base_url}/GetToken/"
        token_payload = {"AppId": app_id, "AppVersion": "", "OsVersion": "", "Platform": "HomeAssistant"}

        try:
            token_json = _post_json(session, token_url, json_body=token_payload)
            public_key_b64 = token_json["PublicKey"]
            public_key_bytes = b64decode(public_key_b64)
        except (KeyError, requests.RequestException, ValueError) as err:
            raise ValueError(f"Failed to obtain public key from {token_url}") from err

        # Fetch account/calendar
        _LOGGER.debug("Fetching waste data from Omrin provider=%s", provider)

        request_body = {
            "a": False,
            "Email": None,
            "Password": None,
            "PostalCode": corrected_postal_code,
            "HouseNumber": street_number,
            "Suffix": suffix,
        }

        try:
            rsa_public_key = RSA.import_key(public_key_bytes)
            encrypted = pkcs1.encrypt(json.dumps(request_body, separators=(",", ":")).encode("utf-8"), rsa_public_key)
            encoded = b64encode(encrypted).decode("utf-8")

            fetch_url = f"{base_url}/FetchAccount/{app_id}"
            # API expects a JSON string body containing the base64 payload (including quotes).
            fetch_json = _post_json(session, fetch_url, data=f"\"{encoded}\"")

            calendar = fetch_json.get("CalendarV2", [])
        except (requests.RequestException, ValueError) as err:
            raise ValueError(f"Failed to fetch waste data from {base_url}") from err

    if not calendar:
        _LOGGER.error("No waste data found for provider=%s postal_code=%s house=%s", provider, corrected_postal_code, street_number)
        return []

    waste_data: list[dict[str, str]] = []
    for item in calendar:
        raw_date = item.get("Datum")
        if not raw_date or raw_date == "0001-01-01T00:00:00":
            continue

        desc = (item.get("Omschrijving") or "").strip().lower()
        waste_type = waste_type_rename(desc)
        if not waste_type:
            continue

        # Omrin returns ISO-like datetime with timezone (e.g. 2025-01-01T00:00:00+0100)
        try:
            dt = datetime.strptime(raw_date, "%Y-%m-%dT%H:%M:%S%z")
            date_str = dt.date().isoformat()
        except ValueError:
            # Be tolerant: some APIs return without tz
            try:
                dt = datetime.strptime(raw_date, "%Y-%m-%dT%H:%M:%S")
                date_str = dt.date().isoformat()
            except ValueError:
                _LOGGER.debug("Skipping item with unparseable date: %r", raw_date)
                continue

        waste_data.append({"type": waste_type, "date": date_str})

    return waste_data
