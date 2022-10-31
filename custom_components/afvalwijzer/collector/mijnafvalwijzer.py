from datetime import datetime

import requests

from ..common.main_functions import _waste_type_rename
from ..const.const import (
    _LOGGER,
    SENSOR_COLLECTOR_TO_URL,
    SENSOR_COLLECTORS_AFVALWIJZER,
)


def get_waste_data_raw(
    provider,
    postal_code,
    street_number,
    suffix,
):
    if provider not in SENSOR_COLLECTORS_AFVALWIJZER:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    if provider == "rova":
        provider = "inzamelkalender.rova"

    try:
        url = SENSOR_COLLECTOR_TO_URL["afvalwijzer_data_default"][0].format(
            provider,
            postal_code,
            street_number,
            suffix,
            datetime.now().strftime("%Y-%m-%d"),
        )

        raw_response = requests.get(url)
    except requests.exceptions.RequestException as err:
        raise ValueError(err) from err

    try:
        response = raw_response.json()
    except ValueError as e:
        raise ValueError(f"Invalid and/or no data received from {url}") from e

    if not response:
        _LOGGER.error("Address not found!")
        return

    try:
        waste_data_raw = (
            response["ophaaldagen"]["data"] + response["ophaaldagenNext"]["data"]
        )
    except KeyError as exc:
        raise KeyError(f"Invalid and/or no data received from {url}") from exc

    return waste_data_raw


if __name__ == "__main__":
    print("Yell something at a mountain!")
