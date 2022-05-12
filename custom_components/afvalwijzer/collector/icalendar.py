from datetime import datetime, timedelta
import re

import requests

from ..common.day_sensor_data import DaySensorData
from ..common.next_sensor_data import NextSensorData
from ..const.const import _LOGGER, SENSOR_COLLECTORS_ICALENDAR


class IcalendarCollector(object):
    DATE_PATTERN = re.compile(r"^\d{8}")

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

        if self.provider not in SENSOR_COLLECTORS_ICALENDAR.keys():
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
            url = SENSOR_COLLECTORS_ICALENDAR[self.provider].format(
                self.provider,
                self.postal_code,
                self.street_number,
                self.suffix,
                datetime.today().strftime("%Y-%m-%d"),
            )
            raw_response = requests.get(url)
            text_response = raw_response.text

        except requests.exceptions.RequestException as err:
            raise ValueError(err)

        waste_data_raw = []

        date = None
        type = None
        for line in text_response.splitlines():
            key, value = line.split(":", 2)
            field = key.split(";")[0]
            if field == "BEGIN" and value == "VEVENT":
                date = None
                type = None
            elif field == "SUMMARY":
                type = value.strip().lower()
            elif field == "DTSTART":
                if self.DATE_PATTERN.match(value):
                    date = f"{value[0:4]}-{value[4:6]}-{value[6:8]}"
                else:
                    _LOGGER.debug("Unsupported date format: %s", value)
            elif field == "END" and value == "VEVENT":
                if date and type:
                    waste_data_raw.append({"type": type, "date": date})
                else:
                    _LOGGER.debug(
                        "No date or type extracted from event: date=%s, type=%s",
                        date,
                        type,
                    )

        # waste_data_raw structure is equal to that in mijnafvalwijzer.py, so code below is also the same

        try:
            waste_data_with_today = {}
            waste_data_without_today = {}

            for item in waste_data_raw:
                item_date = datetime.strptime(item["date"], "%Y-%m-%d")
                item_name = item["type"].strip().lower()
                if item_name not in self.exclude_list:
                    if item_name not in waste_data_with_today:
                        if item_date >= self.DATE_TODAY:
                            waste_data_with_today[item_name] = item_date

            for item in waste_data_raw:
                item_date = datetime.strptime(item["date"], "%Y-%m-%d")
                item_name = item["type"].strip().lower()
                if item_name not in self.exclude_list:
                    if item_name not in waste_data_without_today:
                        if item_date > self.DATE_TODAY:
                            waste_data_without_today[item_name] = item_date

            try:
                for item in waste_data_raw:
                    item_name = item["type"].strip().lower()
                    if item_name not in self.exclude_list:
                        if item_name not in waste_data_with_today.keys():
                            waste_data_with_today[item_name] = self.default_label
                        if item_name not in waste_data_without_today.keys():
                            waste_data_without_today[item_name] = self.default_label
            except Exception as err:
                _LOGGER.error("Other error occurred: %s", err)

            return waste_data_raw, waste_data_with_today, waste_data_without_today
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
