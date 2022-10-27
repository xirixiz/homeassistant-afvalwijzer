from datetime import datetime
import re

import requests

from ..common.waste_data_transformer import WasteDataTransformer
from ..const.const import _LOGGER, SENSOR_COLLECTORS_RD4


class Rd4Collector(object):
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

        if self.provider not in SENSOR_COLLECTORS_RD4.keys():
            raise ValueError(f"Invalid provider: {self.provider}, please verify")

        TODAY = datetime.now()
        self.YEAR_CURRENT = TODAY.year

        self._get_waste_data_provider()

    def __waste_type_rename(self, item_name):
        if item_name == "pruning":
            item_name = "takken"
        if item_name == "residual_waste":
            item_name = "restafval"
        if item_name == "best_bag":
            item_name = "best-tas"
        if item_name == "paper":
            item_name = "papier"
        if item_name == "christmas_trees":
            item_name = "kerstbomen"
        return item_name

    def _get_waste_data_provider(self):

        corrected_postal_code_parts = re.search(
            r"(\d\d\d\d) ?([A-z][A-z])", self.postal_code
        )
        corrected_postal_code = (
            f"{corrected_postal_code_parts[1]}+{corrected_postal_code_parts[2].upper()}"
        )

        try:
            url = SENSOR_COLLECTORS_RD4[self.provider].format(
                corrected_postal_code,
                self.street_number,
                self.suffix,
                self.YEAR_CURRENT,
            )
            raw_response = requests.get(url)
        except requests.exceptions.RequestException as err:
            raise ValueError(err) from err

        try:
            response = raw_response.json()
        except ValueError as e:
            raise ValueError(f"Invalid and/or no data received from {url}") from e

        if not response:
            _LOGGER.error("No waste data found!")
            return

        if not response["success"]:
            _LOGGER.error("Address not found!")
            return

        try:
            waste_data_raw_temp = response["data"]["items"][0]
        except KeyError as exc:
            raise KeyError(f"Invalid and/or no data received from {url}") from exc

        self.waste_data_raw = []

        for item in waste_data_raw_temp:
            if not item["date"]:
                continue

            waste_type = item["type"]
            if not waste_type:
                continue

            temp = {"type": self.__waste_type_rename(item["type"].strip().lower())}
            temp["date"] = datetime.strptime(item["date"], "%Y-%m-%d").strftime(
                "%Y-%m-%d"
            )
            self.waste_data_raw.append(temp)

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
