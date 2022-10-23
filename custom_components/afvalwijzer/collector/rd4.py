from datetime import datetime, timedelta
from os import system
import re

import requests

from ..common.day_sensor_data import DaySensorData
from ..common.next_sensor_data import NextSensorData
from ..const.const import _LOGGER, SENSOR_COLLECTORS_RD4

RD4_API_TEMPLATE = "https://data.rd4.nl/api/v1/waste-calendar?postal_code={}&house_number={}&house_number_extension={}&year={}"


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

        if self.provider != SENSOR_COLLECTORS_RD4:
            raise ValueError("Invalid provider: %s, please verify", self.provider)

        TODAY_DT = datetime.today()
        TODAY_STR = TODAY_DT.strftime("%d-%m-%Y")
        self.DATE_TODAY = datetime.strptime(TODAY_STR, "%d-%m-%Y")
        self.DATE_TOMORROW = datetime.strptime(TODAY_STR, "%d-%m-%Y") + timedelta(
            days=1
        )
        self.YEAR_CURRENT = TODAY_DT.year
        self.YEAR_NEXT = TODAY_DT.year + 1

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

        corrected_postal_code_parts = re.search(
            r"(\d\d\d\d) ?([A-z][A-z])", self.postal_code
        )
        corrected_postal_code = (
            corrected_postal_code_parts.group(1)
            + "+"
            + corrected_postal_code_parts.group(2).upper()
        )

        try:
            url = RD4_API_TEMPLATE.format(
                corrected_postal_code,
                self.street_number,
                self.suffix,
                self.YEAR_CURRENT,
            )
            waste_data_raw = requests.get(url).json()
        except ValueError:
            raise ValueError("Invalid and/or no JSON data received from " + url)

        if waste_data_raw["success"] != True:
            raise ValueError(
                "No waste data received from RD4: " + waste_data_raw["message"]
            )

        try:
            waste_data_with_today = {}
            waste_data_without_today = {}
            waste_data_raw_formatted = []

            data_raw = waste_data_raw["data"]["items"][0]

            for item in data_raw:
                temp = {}
                if not item["date"]:
                    continue

                waste_type = item["type"]
                if not waste_type:
                    continue

                temp["type"] = item["type"].strip().lower()
                temp["date"] = datetime.strptime(item["date"], "%Y-%m-%d").strftime(
                    "%Y-%m-%d"
                )
                waste_data_raw_formatted.append(temp)

            # Try to get the dates of next year as well so we have a smooth transition into the next year
            try:
                url = RD4_API_TEMPLATE.format(
                    corrected_postal_code,
                    self.street_number,
                    self.suffix,
                    self.YEAR_NEXT,
                )
                waste_data_raw_next_year = requests.get(url).json()
            except ValueError:
                _LOGGER.info("No calendar is ready for the year %s yet", self.YEAR_NEXT)

            if (waste_data_raw_next_year is not None) and (
                waste_data_raw_next_year["success"] == True
            ):
                data_raw_next_year = waste_data_raw_next_year["data"]["items"][0]

                for item in data_raw_next_year:
                    temp = {}
                    if not item["date"]:
                        continue

                    waste_type = item["type"]
                    if not waste_type:
                        continue

                    temp["type"] = item["type"].strip().lower()
                    temp["date"] = datetime.strptime(item["date"], "%Y-%m-%d").strftime(
                        "%Y-%m-%d"
                    )
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
