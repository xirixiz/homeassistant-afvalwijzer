from datetime import datetime, timedelta
import json
import requests
import logging

from ..const.const import SENSOR_PROVIDER_TO_URL

_LOGGER = logging.getLogger(__name__)


class AfvalWijzer(object):

    ##########################################################################
    #  INIT
    ##########################################################################
    def __init__(
        self,
        provider,
        postal_code,
        street_number,
        suffix,
        include_date_today,
        default_label,
        exclude_list,
    ):
        self.provider = provider
        self.postal_code = postal_code
        self.street_number = street_number
        self.suffix = suffix
        self.include_date_today = include_date_today
        self.default_label = default_label
        self.exclude_list = list(
            waste.strip().lower() for waste in exclude_list.split(",")
        )

        _providers = (
            "mijnafvalwijzer",
            "afvalstoffendienstkalender",
            "rova",
        )
        if self.provider not in _providers:
            print("Invalid provider: %s, please verify", self.provider)

        if self.provider == "rova":
            self.provider = "inzamelkalender.rova"

        ##########################################################################
        #  DATE CALCULATION TODAY, TOMORROW, DAY AFTER TOMORROW
        ##########################################################################

        # Today
        self.today = datetime.today().strftime("%d-%m-%Y")

        #  DEVELOPMENT MODE
        self.development_mode = False
        if self.development_mode:
            print("\n##### DEVELOPMENT MODE #####")
            self.today = "17-11-2021"
        # END DEVELOPMENT MODE

        # Get and format dates
        self.today_date = datetime.strptime(self.today, "%d-%m-%Y")
        self.tomorrow_date = datetime.strptime(self.today, "%d-%m-%Y") + timedelta(
            days=1
        )
        # Day after Tomorow
        self.day_after_tomorrow_date = datetime.strptime(
            self.today, "%d-%m-%Y"
        ) + timedelta(days=2)

        if self.include_date_today.casefold() in ("true", "yes"):
            self.date_selected = self.today_date
        else:
            self.date_selected = self.tomorrow_date

        ##########################################################################
        #  GET AND GENERATE DATA
        ##########################################################################

        # Get waste data list of dicts from provider
        self.waste_data_raw = self._get_waste_data_raw()
        # Generate waste types list
        self.waste_types_provider = self._get_waste_types_provider()
        # Generate waste types list, without excluded
        self.waste_types_provider_included = self._get_waste_types_provider_included()
        # Generate waste data list of dicts, without excluded and datetime formatted
        self.waste_data_formatted = self._gen_waste_data_formatted()
        # Generate waste data list of dicts using date_selected, without excluded and datetime formatted
        self.waste_data_after_date_selected = self._gen_waste_data_after_date_selected()
        # Get next waste date
        self.next_waste_date = self._get_next_waste_date()
        # Get next waste type
        self.next_waste_type = self._get_next_waste_type()
        # Get next waste date in days
        self.next_waste_in_days = self._get_next_waste_in_days()
        # Get Today sensor data
        self.waster_data_today = self._gen_day_sensor(self.today_date)
        # Get Tomorrow sensor data
        self.waster_data_tomorrow = self._gen_day_sensor(self.tomorrow_date)
        # Get Day after Tomorrow sensor data
        self.waster_data_dot = self._gen_day_sensor(self.day_after_tomorrow_date)

        ##########################################################################
        #  GENERATE SENSOR DATA
        ##########################################################################
        self.waste_data_with_today = self._gen_waste_data_provider(self.today_date)
        self.waste_data_without_today = self._gen_waste_data_provider(
            self.tomorrow_date
        )
        self.waste_data_custom = dict(
            **self._gen_next_sensor_data(), **self._gen_day_sensor_data()
        )
        self.waste_types_provider = self.waste_types_provider_included
        self.waste_types_custom = self._get_waste_types_custom()

    ##########################################################################
    #  GET DATA LISTS OF DICTS FROM PROVIDER
    ##########################################################################

    # Get all data in JSON format from provider
    def _get_waste_data_raw(self):
        try:
            if not self.development_mode:
                _LOGGER.debug("Connecting to: %s", self.provider)

                url = SENSOR_PROVIDER_TO_URL["afvalwijzer_data_default"][0].format(
                    self.provider,
                    self.postal_code,
                    self.street_number,
                    self.suffix,
                    datetime.today().strftime("%Y-%m-%d"),
                )

                _LOGGER.debug("URL parsed: %s", url)

                try:
                    raw_response = requests.get(url)
                except requests.exceptions.RequestException as err:
                    raise ValueError(err)

                try:
                    json_response = raw_response.json()
                except ValueError:
                    raise ValueError("No JSON data received from " + url)

                try:
                    waste_data_raw = (
                        json_response["ophaaldagen"]["data"]
                        + json_response["ophaaldagenNext"]["data"]
                    )
                except ValueError:
                    raise ValueError("Invalid and/or no JSON data received from " + url)

                if not waste_data_raw:
                    _LOGGER.error("No waste data found!")
                    return
            else:
                waste_data_raw = json.load(
                    open("afvalwijzer/test_data/dummy_data.json")
                )

            # Strip and lowercase all provider values
            waste_data_raw = list(
                {key.strip().lower(): value for key, value in waste.items()}
                for waste in waste_data_raw
            )

        except Exception as err:
            _LOGGER.error("Other error occurred _get_waste_data_raw: %s", err)

        # Returns JSON object as a dictionary
        return waste_data_raw

    ##########################################################################
    #  PROCESS WASTE DATA FROM PROVIDER - LISTS
    ##########################################################################

    # Generate waste types list
    def _get_waste_types_provider(self):
        try:
            waste_types_provider = sorted(
                set(list(waste["type"] for waste in self.waste_data_raw))
            )
        except Exception as err:
            _LOGGER.error("Other error occurred _get_waste_types_provider: %s", err)
        return waste_types_provider

    # Generate waste types custom list
    def _get_waste_types_custom(self):
        try:
            waste_types_custom = list(sorted(self.waste_data_custom.keys()))
        except Exception as err:
            _LOGGER.error("Other error occurred _get_waste_types_custom: %s", err)
        return waste_types_custom

    # Generate waste types list, without excluded
    def _get_waste_types_provider_included(self):
        try:
            waste_types_provider_included = list(
                sorted(set(self.waste_types_provider) - set(self.exclude_list))
            )
        except Exception as err:
            _LOGGER.error(
                "Other error occurred _get_waste_types_provider_included: %s", err
            )
        return waste_types_provider_included

    # Generate waste data list of dicts after Today, without excluded and datetime formatted
    def _gen_waste_data_formatted(self):
        try:
            waste_data_formatted = list(
                {
                    "type": waste["type"],
                    "date": datetime.strptime(waste["date"], "%Y-%m-%d"),
                }
                for waste in self.waste_data_raw
                if waste["type"] in self.waste_types_provider_included
            )
        except Exception as err:
            _LOGGER.error("Other error occurred _gen_waste_data_formatted: %s", err)
        return waste_data_formatted

    # Remove history from the list of dicts before date_selected
    def _gen_waste_data_after_date_selected(self):
        try:
            waste_data_after_date_selected = list(
                filter(
                    lambda waste: waste["date"] >= self.date_selected,
                    self.waste_data_formatted,
                )
            )
        except Exception as err:
            _LOGGER.error(
                "Other error occurred _gen_waste_data_after_date_selected: %s", err
            )
        return waste_data_after_date_selected

    ##########################################################################
    #  PROCESS WASTE DATA FROM PROVIDER - SENSOR DATA
    ##########################################################################

    # Generate sensor data for waste types, without excluded
    def _gen_waste_data_provider(self, date):
        waste_data_provider = dict()
        try:
            for waste in self.waste_data_formatted:
                item_date = waste["date"]
                item_name = waste["type"]
                if item_date >= date:
                    if item_name not in waste_data_provider.keys():
                        if isinstance(item_date, datetime):
                            waste_data_provider[item_name] = item_date
                        else:
                            waste_data_provider[item_name] = self.default_label
            for waste in self.waste_data_formatted:
                item_name = waste["type"]
                if item_name not in waste_data_provider.keys():
                    waste_data_provider[item_name] = self.default_label
        except Exception as err:
            _LOGGER.error("Other error occurred _gen_waste_data_provider: %s", err)
        return waste_data_provider

    ##########################################################################
    #  CREATE TODAY, TOMORROW, DOT SENSOR(S)
    ##########################################################################

    def _gen_day_sensor(self, date):
        day = list()
        try:
            for waste in self.waste_data_formatted:
                item_date = waste["date"]
                item_name = waste["type"]
                if item_date == date:
                    day.append(item_name)
            if not day:
                day.append(self.default_label)
        except Exception as err:
            _LOGGER.error("Other error occurred _gen_day_sensor: %s", err)
        return day

    # Generate sensor data for today, tomorrow, day after tomorrow
    def _gen_day_sensor_data(self):
        day_sensor = dict()
        try:
            day_sensor["today"] = ", ".join(self.waster_data_today)
            day_sensor["tomorrow"] = ", ".join(self.waster_data_tomorrow)
            day_sensor["day_after_tomorrow"] = ", ".join(self.waster_data_dot)
        except Exception as err:
            _LOGGER.error("Other error occurred _gen_day_sensor_data: %s", err)
        return day_sensor

    ##########################################################################
    #  CREATE NEXT SENSOR(S)
    ##########################################################################

    # Generate sensor next_waste_date
    def _get_next_waste_date(self):
        next_waste_date = self.default_label
        try:
            next_waste_date = self.waste_data_after_date_selected[0]["date"]
        except Exception as err:
            _LOGGER.error("Other error occurred _get_next_waste_date: %s", err)
        return next_waste_date

    # Generate sensor next_waste_in_days
    def _get_next_waste_in_days(self):
        next_waste_in_days = self.default_label
        try:
            next_waste_in_days = abs(self.today_date - self.next_waste_date).days
        except Exception as err:
            _LOGGER.error("Other error occurred _get_next_waste_in_days: %s", err)
        return next_waste_in_days

    # Generate sensor next_waste_type
    def _get_next_waste_type(self):
        next_waste_type = list()
        try:
            for waste in self.waste_data_after_date_selected:
                item_date = waste["date"]
                item_name = waste["type"]
                if item_date == self.next_waste_date:
                    next_waste_type.append(item_name)
            if not next_waste_type:
                next_waste_type.append(self.default_label)
        except Exception as err:
            _LOGGER.error("Other error occurred _get_next_waste_type: %s", err)
        return next_waste_type

    # Generate sensor data for custom sensors
    def _gen_next_sensor_data(self):
        next_sensor = dict()
        try:
            next_sensor["next_waste_date"] = self.next_waste_date
            next_sensor["next_waste_type"] = ", ".join(self.next_waste_type)
            next_sensor["next_waste_in_days"] = self.next_waste_in_days
        except Exception as err:
            _LOGGER.error("Other error occurred _gen_next_sensor_data: %s", err)
        return next_sensor
