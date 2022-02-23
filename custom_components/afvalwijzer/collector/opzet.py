from datetime import datetime, timedelta
from os import system

import requests

from ..common.day_sensor_data import DaySensorData
from ..common.next_sensor_data import NextSensorData
from ..const.const import _LOGGER, SENSOR_COLLECTORS_OPZET


class OpzetCollector(object):
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

        if self.provider not in SENSOR_COLLECTORS_OPZET.keys():
            raise ValueError("Invalid provider: %s, please verify", self.provider)

        TODAY = datetime.today().strftime("%d-%m-%Y")
        self.DATE_TODAY = datetime.strptime(TODAY, "%d-%m-%Y")
        self.DATE_TOMORROW = datetime.strptime(TODAY, "%d-%m-%Y") + timedelta(days=1)

        (
            self._waste_data_raw,
            self._waste_data_with_today,
            self._waste_data_without_today,
        ) = self.get_waste_data_provider()

        (
            self._waste_data_provider,
            self._waste_types_provider,
            self._waste_data_custom,
            self._waste_types_custom,
        ) = self.transform_waste_data()

    def get_waste_data_provider(self):
        try:
            self.bag_id = None
            if self.provider == "suez":
                self._verify = False
            else:
                self._verify = True

            url = "{}/rest/adressen/{}-{}".format(
                SENSOR_COLLECTORS_OPZET[self.provider],
                self.postal_code,
                self.street_number,
                verify=self._verify,
            )

            json_response = requests.get(url).json()

            if not json_response:
                _LOGGER.error("Address not found!")
                return

        except ValueError:
            raise ValueError("No JSON data received from " + url)

        try:
            if len(json_response) > 1 and self.suffix:
                for item in json_response:
                    if (
                        item["huisletter"] == self.suffix
                        or item["huisnummerToevoeging"] == self.suffix
                    ):
                        self.bag_id = item["bagId"]
                        break
            else:
                self.bag_id = json_response[0]["bagId"]

            url = "{}/rest/adressen/{}/afvalstromen".format(
                SENSOR_COLLECTORS_OPZET[self.provider],
                self.bag_id,
                verify=self._verify,
            )
            waste_data_raw = requests.get(url).json()
        except ValueError:
            raise ValueError("Invalid and/or no JSON data received from " + url)

        try:
            waste_data_with_today = {}
            waste_data_without_today = {}
            waste_data_raw_formatted = []

            for item in waste_data_raw:
                temp = {}
                if not item["ophaaldatum"]:
                    continue

                waste_type = item["menu_title"]
                if not waste_type:
                    continue

                temp["type"] = self.__waste_type_rename(
                    item["menu_title"].strip().lower()
                )
                temp["date"] = datetime.strptime(
                    item["ophaaldatum"], "%Y-%m-%d"
                ).strftime("%Y-%m-%d")
                waste_data_raw_formatted.append(temp)

            for item in waste_data_raw_formatted:
                item_date = datetime.strptime(item["date"], "%Y-%m-%d")
                item_name = item["type"]
                if item_name not in self.exclude_list:
                    if item_name not in waste_data_with_today:
                        if item_date >= self.DATE_TODAY:
                            waste_data_with_today[item_name] = item_date

            for item in waste_data_raw_formatted:
                item_date = datetime.strptime(item["date"], "%Y-%m-%d")
                item_name = item["type"]
                if item_name not in self.exclude_list:
                    if item_name not in waste_data_without_today:
                        if item_date > self.DATE_TODAY:
                            waste_data_without_today[item_name] = item_date

            try:
                for item in waste_data_raw_formatted:
                    item_name = item["type"]
                    if item_name not in self.exclude_list:
                        if item_name not in waste_data_with_today.keys():
                            waste_data_with_today[item_name] = self.default_label
                        if item_name not in waste_data_without_today.keys():
                            waste_data_without_today[item_name] = self.default_label
            except Exception as err:
                _LOGGER.error("Other error occurred: %s", err)

            return (
                waste_data_raw_formatted,
                waste_data_with_today,
                waste_data_without_today,
            )
        except Exception as err:
            _LOGGER.error("Other error occurred: %s", err)

    def __waste_type_rename(self, item_name):
        if item_name == "snoeiafval":
            item_name = "takken"
        if item_name == "sloop":
            item_name = "grofvuil"
        if item_name == "glas":
            item_name = "glas"
        if item_name == "duobak":
            item_name = "duobak"
        if item_name == "groente":
            item_name = "gft"
        if item_name == "groente-, fruit en tuinafval":
            item_name = "gft"
        if item_name == "gft":
            item_name = "gft"
        if item_name == "chemisch":
            item_name = "chemisch"
        if item_name == "kca":
            item_name = "chemisch"
        if item_name == "tariefzak restafval":
            item_name = "restafvalzakken"
        if item_name == "restafvalzakken":
            item_name = "restafvalzakken"
        if item_name == "rest":
            item_name = "restafval"
        if item_name == "plastic":
            item_name = "plastic"
        if item_name == "plastic, blik & drinkpakken overbetuwe":
            item_name = "pmd"
        if item_name == "papier":
            item_name = "papier"
        if item_name == "papier en karton":
            item_name = "papier"
        if item_name == "pmd":
            item_name = "pmd"
        if item_name == "textiel":
            item_name = "textiel"
        if item_name == "kerstb":
            item_name = "kerstboom"
        return item_name

    ##########################################################################
    #  COMMON CODE
    ##########################################################################
    def transform_waste_data(self):
        if self.exclude_pickup_today.casefold() in ("false", "no"):
            date_selected = self.DATE_TODAY
            waste_data_provider = self._waste_data_with_today
        else:
            date_selected = self.DATE_TOMORROW
            waste_data_provider = self._waste_data_without_today

        try:
            waste_types_provider = sorted(
                set(
                    list(
                        waste["type"]
                        for waste in self.waste_data_raw
                        if waste["type"] not in self.exclude_list
                    )
                )
            )
        except Exception as err:
            _LOGGER.error("Other error occurred waste_types_provider: %s", err)

        try:
            waste_data_formatted = list(
                {
                    "type": waste["type"],
                    "date": datetime.strptime(waste["date"], "%Y-%m-%d"),
                }
                for waste in self.waste_data_raw
                if waste["type"] in waste_types_provider
            )
        except Exception as err:
            _LOGGER.error("Other error occurred waste_data_formatted: %s", err)

        days = DaySensorData(waste_data_formatted, self.default_label)

        try:
            waste_data_after_date_selected = list(
                filter(
                    lambda waste: waste["date"] >= date_selected, waste_data_formatted
                )
            )
        except Exception as err:
            _LOGGER.error(
                "Other error occurred waste_data_after_date_selected: %s", err
            )

        next = NextSensorData(waste_data_after_date_selected, self.default_label)

        try:
            waste_data_custom = {**next.next_sensor_data, **days.day_sensor_data}
        except Exception as err:
            _LOGGER.error("Other error occurred waste_data_custom: %s", err)

        try:
            waste_types_custom = list(sorted(waste_data_custom.keys()))
        except Exception as err:
            _LOGGER.error("Other error occurred waste_types_custom: %s", err)

        return (
            waste_data_provider,
            waste_types_provider,
            waste_data_custom,
            waste_types_custom,
        )

    ##########################################################################
    #  PROPERTIES FOR EXECUTION
    ##########################################################################
    @property
    def waste_data_raw(self):
        return self._waste_data_raw

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
