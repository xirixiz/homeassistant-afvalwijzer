from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Tuple

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..const.const import _LOGGER, SENSOR_COLLECTORS_MIJNAFVALWIJZER
from ..common.main_functions import format_postal_code


requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: Tuple[float, float] = (5.0, 60.0)


def _build_url(
    provider: str,
    postal_code: str,
    street_number: str,
    suffix: str,
) -> str:
    if provider not in SENSOR_COLLECTORS_MIJNAFVALWIJZER:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    corrected_postal_code = format_postal_code(postal_code)

    return SENSOR_COLLECTORS_MIJNAFVALWIJZER[provider].format(
        corrected_postal_code,
        street_number,
        suffix,
        datetime.now().strftime("%Y-%m-%d"),
    )


def _fetch_data(
    session: requests.Session,
    url: str,
    *,
    timeout: Tuple[float, float],
    verify: bool,
) -> Dict:
    response = session.get(
        url,
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()
    return response.json()


def _parse_waste_data_raw(response: Dict) -> List[Dict]:
    ophaaldagen_data = response.get("ophaaldagen", {}).get("data", [])
    ophaaldagen_next_data = response.get("ophaaldagenNext", {}).get("data", [])

    if not ophaaldagen_data and not ophaaldagen_next_data:
        raise KeyError("No ophaaldagen data found")

    # Keep original behavior: limit next items to 25
    return ophaaldagen_data + ophaaldagen_next_data[:25]


def get_waste_data_raw(
    provider: str,
    postal_code: str,
    street_number: str,
    suffix: str,
    *,
    session: requests.Session | None = None,
    timeout: Tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
) -> List[Dict]:
    """
    Collector-style function:
    - Always returns `waste_data_raw`
    - Naming aligned with other collectors
    - Clear fetch → parse → return flow
    """
    session = session or requests.Session()
    url = _build_url(provider, postal_code, street_number, suffix)

    try:
        response = _fetch_data(
            session,
            url,
            timeout=timeout,
            verify=verify,
        )

        waste_data_raw = _parse_waste_data_raw(response)

        return waste_data_raw

    except requests.exceptions.RequestException as err:
        _LOGGER.error("MijnAfvalWijzer request error: %s", err)
        raise ValueError(err) from err
    except KeyError as err:
        _LOGGER.error("MijnAfvalWijzer invalid response from %s", url)
        raise KeyError(f"Invalid and/or no data received from {url}") from err
