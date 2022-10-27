from datetime import datetime
import re

import requests

from ..common.waste_data_transformer import WasteDataTransformer
from ..const.const import _LOGGER, SENSOR_COLLECTORS_DEAFVALAPP


class DeAfvalappCollector(object):
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

        if self.provider not in SENSOR_COLLECTORS_DEAFVALAPP.keys():
            raise ValueError(f"Invalid provider: {self.provider}, please verify")

        self._get_waste_data_provider()

    def __waste_type_rename(self, item_name):
        if item_name == "gemengde plastics":
            item_name = "plastic"
        if item_name == "zak_blauw":
            item_name = "restafval"
        if item_name == "pbp":
            item_name = "pmd"
        if item_name == "rest":
            item_name = "restafval"
        if item_name == "kerstboom":
            item_name = "kerstbomen"
        return item_name

    def _get_waste_data_provider(self):

        corrected_postal_code_parts = re.search(
            r"(\d\d\d\d) ?([A-z][A-z])", self.postal_code
        )
        corrected_postal_code = (
            corrected_postal_code_parts[1] + corrected_postal_code_parts[2].upper()
        )

        try:
            url = SENSOR_COLLECTORS_DEAFVALAPP[self.provider].format(
                corrected_postal_code,
                self.street_number,
                self.suffix,
            )
            raw_response = requests.get(url)
        except requests.exceptions.RequestException as err:
            raise ValueError(err) from err

        try:
            response = raw_response.text
        except ValueError as e:
            raise ValueError(f"Invalid and/or no data received from {url}") from e

        if not response:
            _LOGGER.error("No waste data found!")
            return

        self.waste_data_raw = []

        for rows in response.strip().split("\n"):
            for ophaaldatum in rows.split(";")[1:-1]:
                temp = {
                    "type": self.__waste_type_rename(rows.split(";")[0].strip().lower())
                }
                temp["date"] = datetime.strptime(ophaaldatum, "%d-%m-%Y").strftime(
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
