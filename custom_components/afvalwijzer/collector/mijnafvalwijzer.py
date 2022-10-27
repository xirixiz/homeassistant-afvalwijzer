from datetime import datetime

import requests

from ..common.waste_data_transformer import WasteDataTransformer
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
            raise ValueError("Invalid provider: %s, please verify", self.provider)

        if self.provider == "rova":
            self.provider = "inzamelkalender.rova"

        self._get_waste_data_provider()

    def _get_waste_data_provider(self):
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

        ##########################################################################
        #  COMMON CODE
        ##########################################################################
        waste_data = WasteDataTransformer(
            self.waste_data_raw,
            self.exclude_pickup_today,
            self.exclude_list,
            self.default_label,
        )

        self._waste_data_with_today = waste_data.waste_data_with_today
        self._waste_data_without_today = waste_data.waste_data_without_today
        self._waste_data_custom = waste_data.waste_data_custom
        self._waste_data_provider = waste_data.waste_data_provider
        self._waste_types_provider = waste_data.waste_types_provider
        self._waste_types_custom = waste_data.waste_types_custom

    ##########################################################################
    #  PROPERTIES FOR EXECUTION
    ##########################################################################
    @property
    def waste_data_with_today(self):
        return self._waste_data_with_today

    @property
    def waste_data_without_today(self):
        return self._waste_data_without_today

    @property
    def waste_data_provider(self):
        return self._waste_data_provider

    @property
    def waste_types_provider(self):
        return self._waste_types_provider

    @property
    def waste_data_custom(self):
        return self._waste_data_custom

    @property
    def waste_types_custom(self):
        return self._waste_types_custom
