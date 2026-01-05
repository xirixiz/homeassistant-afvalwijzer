from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..const.const import _LOGGER
# from ..const.const import SENSOR_COLLECTORS_<NAME>
# from ..common.main_functions import format_postal_code, waste_type_rename, ...


requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: Tuple[float, float] = (5.0, 20.0)


def _build_url(provider: str, postal_code: str, street_number: str, suffix: str) -> str:
    """
    - validate provider
    - normalize postal code if needed
    - build base url or full url
    """
    raise NotImplementedError


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    url: str,
    *,
    timeout: Tuple[float, float],
    verify: bool,
) -> Any:
    """
    Do the HTTP work (GET/POST/GraphQL/etc) and return the raw response payload
    or the temp list to parse (waste_data_raw_temp).
    """
    raise NotImplementedError


def _parse_waste_data_raw(waste_data_raw_temp: Any) -> List[Dict[str, Any]]:
    """
    Convert API-specific output into a list[dict] where each dict matches your common schema.
    Keep collector naming: waste_data_raw_temp -> waste_data_raw
    """
    raise NotImplementedError


def get_waste_data_raw(
    provider: str,
    postal_code: str,
    street_number: str,
    suffix: str,
    *,
    session: Optional[requests.Session] = None,
    timeout: Tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
) -> List[Dict[str, Any]]:
    """
    Collector-style:
    - always returns waste_data_raw
    - linear flow: url -> fetch temp -> parse -> return
    - wrap requests errors as ValueError (consistent with existing collectors)
    """
    session = session or requests.Session()
    url = _build_url(provider, postal_code, street_number, suffix)

    try:
        waste_data_raw_temp = _fetch_waste_data_raw_temp(
            session,
            url,
            timeout=timeout,
            verify=verify,
        )

        waste_data_raw = _parse_waste_data_raw(waste_data_raw_temp)
        return waste_data_raw

    except requests.exceptions.RequestException as err:
        _LOGGER.error("%s request error: %s", __name__, err)
        raise ValueError(err) from err
    except KeyError as err:
        _LOGGER.error("%s invalid response from %s", __name__, url)
        raise
