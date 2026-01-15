from __future__ import annotations

from typing import Any

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..const.const import _LOGGER

# from ..const.const import SENSOR_COLLECTORS_<NAME>
# from ..common.main_functions import format_postal_code, waste_type_rename, ...


requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 20.0)


def _build_url(provider: str, postal_code: str, street_number: str, suffix: str) -> str:
    """Build and validate the request URL.

    Validate the provider, normalize the postal code if needed, and build the base
    or full URL for the collector request.
    """
    raise NotImplementedError


def _fetch_waste_data_raw_temp(
    session: requests.Session,
    url: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> Any:
    """Fetch the raw response payload for the collector.

    Perform the HTTP work (GET, POST, GraphQL, etc.) and return the raw response
    payload or an intermediate structure (waste_data_raw_temp) that can be parsed.
    """
    raise NotImplementedError


def _parse_waste_data_raw(waste_data_raw_temp: Any) -> list[dict[str, Any]]:
    """Parse provider output into the common waste schema.

    Convert API specific output into a list of dicts where each dict matches the
    common schema. Keep collector naming: waste_data_raw_temp becomes waste_data_raw.
    """
    raise NotImplementedError


def get_waste_data_raw(
    provider: str,
    postal_code: str,
    street_number: str,
    suffix: str,
    *,
    session: requests.Session | None = None,
    timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
) -> list[dict[str, Any]]:
    """Return waste_data_raw."""

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
    except KeyError:
        _LOGGER.error("%s invalid response from %s", __name__, url)
        raise
