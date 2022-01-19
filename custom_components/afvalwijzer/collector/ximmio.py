from datetime import datetime

import requests

from ..common.day_sensor_data import DaySensorData
from ..common.next_sensor_data import NextSensorData
from ..const.const import (
    _LOGGER,
    DATE_TODAY,
    DATE_TODAY_NEXT_YEAR,
    DATE_TOMORROW,
    SENSOR_COLLECTOR_TO_URL,
    SENSOR_COLLECTORS_XIMMIO,
)


class XimmioCollector(object):
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

        if self.provider not in SENSOR_COLLECTORS_XIMMIO.keys():
            raise ValueError("Invalid provider: %s, please verify", self.provider)

        collectors = ("avalex", "meerlanden", "rad", "westland")
        if self.provider in collectors:
            self.provider_url = "ximmio02"
        else:
            self.provider_url = "ximmio01"

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
        ##########################################################################
        # First request: get uniqueId and community
        ##########################################################################
        try:
            url = SENSOR_COLLECTOR_TO_URL[self.provider_url][0]
            companyCode = SENSOR_COLLECTORS_XIMMIO[self.provider]
            data = {
                "postCode": self.postal_code,
                "houseNumber": self.street_number,
                "companyCode": companyCode,
            }

            raw_response = requests.post(url=url, data=data)

            uniqueId = raw_response.json()["dataList"][0]["UniqueId"]
            community = raw_response.json()["dataList"][0]["Community"]

        except requests.exceptions.RequestException as err:
            raise ValueError(err)

        ##########################################################################
        # Second request: get the dates
        ##########################################################################
        try:
            url = SENSOR_COLLECTOR_TO_URL[self.provider_url][1]
            data = {
                "companyCode": companyCode,
                "startDate": DATE_TODAY.date(),
                "endDate": DATE_TODAY_NEXT_YEAR,
                "community": community,
                "uniqueAddressID": uniqueId,
            }
            json_response = requests.post(url=url, data=data).json()

        except ValueError:
            raise ValueError("No JSON data received from " + url)

        try:
            waste_data_raw = json_response["dataList"]
        except ValueError:
            raise ValueError("Invalid and/or no JSON data received from " + url)

        try:
            waste_data_with_today = {}
            waste_data_without_today = {}
            waste_data_raw_formatted = []

            for item in waste_data_raw:
                temp = {}
                temp["type"] = self.__waste_type_rename(
                    item["_pickupTypeText"].strip().lower()
                )
                temp["date"] = datetime.strptime(
                    item["pickupDates"][0], "%Y-%m-%dT%H:%M:%S"
                ).strftime("%Y-%m-%d")
                waste_data_raw_formatted.append(temp)

            for item in waste_data_raw_formatted:
                item_date = datetime.strptime(item["date"], "%Y-%m-%d")
                item_name = item["type"]
                if item_name not in self.exclude_list:
                    if item_name not in waste_data_with_today:
                        if item_date >= DATE_TODAY:
                            waste_data_with_today[item_name] = item_date

            for item in waste_data_raw_formatted:
                item_date = datetime.strptime(item["date"], "%Y-%m-%d")
                item_name = item["type"]
                if item_name not in self.exclude_list:
                    if item_name not in waste_data_without_today:
                        if item_date > DATE_TODAY:
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
        if item_name == "branches":
            item_name = "takken"
        if item_name == "bulklitter":
            item_name = "grofvuil"
        if item_name == "bulkygardenwaste":
            item_name = "tuinafval"
        if item_name == "glass":
            item_name = "glas"
        if item_name == "green":
            item_name = "gft"
        if item_name == "grey":
            item_name = "restafval"
        if item_name == "kca":
            item_name = "chemisch"
        if item_name == "plastic":
            item_name = "plastic"
        if item_name == "packages":
            item_name = "pmd"
        if item_name == "paper":
            item_name = "papier"
        if item_name == "remainder":
            item_name = "restwagen"
        if item_name == "textile":
            item_name = "textiel"
        if item_name == "tree":
            item_name = "kerstboom"
        return item_name

    ##########################################################################
    #  COMMON CODE
    ##########################################################################
    def transform_waste_data(self):
        if self.exclude_pickup_today.casefold() in ("false", "no"):
            date_selected = DATE_TODAY
            waste_data_provider = self._waste_data_with_today
        else:
            date_selected = DATE_TOMORROW
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
