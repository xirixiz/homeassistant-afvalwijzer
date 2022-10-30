from datetime import datetime

import requests

from ..const.const import (
    _LOGGER,
    SENSOR_COLLECTOR_TO_URL,
    SENSOR_COLLECTORS_AFVALWIJZER,
)


class MijnAfvalWijzerCollector(object):
    def __init__(
        self,
        provider,
        postal_code,
        street_number,
        suffix,
        exclude_pickup_today,
        exclude_list,
        default_label,
    ):
        self.provider = provider
        self.postal_code = postal_code
        self.street_number = street_number
        self.suffix = suffix
        self.exclude_pickup_today = exclude_pickup_today
        self.exclude_list = exclude_list.strip().lower()
        self.default_label = default_label

        if self.provider not in SENSOR_COLLECTORS_AFVALWIJZER:
            raise ValueError(f"Invalid provider: {self.provider}, please verify")

        if self.provider == "rova":
            self.provider = "inzamelkalender.rova"

        try:
            url = SENSOR_COLLECTOR_TO_URL["afvalwijzer_data_default"][0].format(
                self.provider,
                self.postal_code,
                self.street_number,
                self.suffix,
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
            self.waste_data_raw = (
                response["ophaaldagen"]["data"] + response["ophaaldagenNext"]["data"]
            )
        except KeyError as exc:
            raise KeyError(f"Invalid and/or no data received from {url}") from exc
