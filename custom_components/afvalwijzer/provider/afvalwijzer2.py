from datetime import datetime, timedelta
import json

import requests
from requests.api import delete

from ..const.const import _LOGGER, SENSOR_PROVIDER_TO_URL


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
        self.exclude_list = exclude_list.split(",")
        self.exclude_list = list(x.strip().lower() for x in self.exclude_list)

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
            print("##### DEVELOPMENT MODE #####")
            self.today = "17-11-2021"
        # END DEVELOPMENT MODE

        self.today_date = datetime.strptime(self.today, "%d-%m-%Y")

        # Tomorow
        self.today_to_tomorrow = datetime.strptime(self.today, "%d-%m-%Y") + timedelta(
            days=1
        )
        self.tomorrow = datetime.strftime(self.today_to_tomorrow, "%d-%m-%Y")
        self.tomorrow_date = datetime.strptime(self.tomorrow, "%d-%m-%Y")

        # Day after Tomorow
        self.today_to_day_after_tomorrow = datetime.strptime(
            self.today, "%d-%m-%Y"
        ) + timedelta(days=2)
        self.day_after_tomorrow = datetime.strftime(
            self.today_to_day_after_tomorrow, "%d-%m-%Y"
        )
        self.day_after_tomorrow_date = datetime.strptime(
            self.day_after_tomorrow, "%d-%m-%Y"
        )

        if self.include_date_today.casefold() in ("true", "yes"):
            self.date_selected = self.today_date
        else:
            self.date_selected = self.tomorrow_date

        ##########################################################################
        #  GET AND GENERATE DATA
        ##########################################################################

        # Get waste data list of dicts from provider
        self.data_raw = self._get_data_provider()
        # Generate waste types list
        self.types = self._get_types()
        # Generate waste types list, without excluded
        self.types_included = self._get_types_included()
        # Generate waste data list of dicts, without excluded and datetime formatted
        self.data_full = self._gen_data_full()
        # Generate waste data list of dicts using date_selected, without excluded and datetime formatted
        self.data_after_date_selected = self._gen_data_after_date_selected()
        # Get next waste date
        self.next_date = self._get_next_date()
        # Get next waste type
        self.next_type = self._get_next_type()
        # Get next waste date in days
        self.next_in_days = self._get_next_in_days()
        # Get Today sensor data
        self.today_sensor_data = self._get_day_sensor(self.today_date)
        # Get Tomorrow sensor data
        self.tomorrow_sensor_data = self._get_day_sensor(self.tomorrow_date)
        # Get Day after Tomorrow sensor data
        self.day_after_tomorrow_sensor_data = self._get_day_sensor(
            self.day_after_tomorrow_date
        )

        ##########################################################################
        #  GENERATE SENSOR DATA
        ##########################################################################
        self.sensor_data_with_today = self._gen_provider_sensor_data(self.today_date)
        self.sensor_data_without_today = self._gen_provider_sensor_data(
            self.tomorrow_date
        )
        self.sensor_data_custom = dict(
            **self._gen_next_sensor_data(), **self._gen_day_sensor_data()
        )
        self.sensor_types = self.types_included
        self.sensor_types_custom = self._get_types_custom()

    ##########################################################################
    #  GET DATA LISTS OF DICTS FROM PROVIDER
    ##########################################################################

    # Get all data in JSON format from provider
    def _get_data_provider(self):
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
                    result = (
                        json_response["ophaaldagen"]["data"]
                        + json_response["ophaaldagenNext"]["data"]
                    )
                except ValueError:
                    raise ValueError("Invalid and/or no JSON data received from " + url)

                if not result:
                    _LOGGER.error("No waste data found!")
                    return
            else:
                result = [
                    {
                        "nameType": "kerstbomen",
                        "type": "kerstbomen",
                        "date": "2021-01-09",
                    },
                    {"nameType": "gft", "type": "gft", "date": "2021-09-24"},
                    {"nameType": "pmd", "type": "pmd", "date": "2021-09-28"},
                    {"nameType": "gft", "type": "gft", "date": "2021-10-08"},
                    {"nameType": "pmd", "type": "pmd", "date": "2021-10-12"},
                    {
                        "nameType": "restafval",
                        "type": "restafval",
                        "date": "2021-10-15",
                    },
                    {"nameType": "papier", "type": "papier", "date": "2021-10-20"},
                    {"nameType": "gft", "type": "gft", "date": "2021-10-22"},
                    {"nameType": "pmd", "type": "pmd", "date": "2021-10-26"},
                    {"nameType": "gft", "type": "gft", "date": "2021-11-05"},
                    {"nameType": "pmd", "type": "pmd", "date": "2021-11-09"},
                    {
                        "nameType": "restafval",
                        "type": "restafval",
                        "date": "2021-11-12",
                    },
                    {"nameType": "papier", "type": "papier", "date": "2021-11-17"},
                    {"nameType": "gft", "type": "gft", "date": "2021-11-19"},
                    {"nameType": "pmd", "type": "pmd", "date": "2021-11-19"},
                    {"nameType": "gft", "type": "gft", "date": "2021-12-03"},
                    {"nameType": "pmd", "type": "pmd", "date": "2021-12-07"},
                    {
                        "nameType": "restafval",
                        "type": "restafval",
                        "date": "2021-12-10",
                    },
                    {"nameType": "papier", "type": "papier", "date": "2021-12-15"},
                    {"nameType": "gft", "type": "gft", "date": "2021-12-18"},
                    {"nameType": "pmd", "type": "pmd", "date": "2021-12-21"},
                    {"nameType": "gft", "type": "gft", "date": "2021-12-31"},
                ]

            # Strip and lowercase all provider values
            result = list({k.strip().lower(): v for k, v in x.items()} for x in result)

        except Exception as err:
            _LOGGER.error("Other error occurred _get_data_provider: %s", err)

        return result

    ##########################################################################
    #  PROCESS WASTE DATA FROM PROVIDER - LISTS
    ##########################################################################

    # Generate waste types list
    def _get_types(self):
        try:
            result = sorted(set(list(x["type"] for x in self.data_raw)))
        except Exception as err:
            _LOGGER.error("Other error occurred _get_types: %s", err)
        return result

    # Generate waste types custom list
    def _get_types_custom(self):
        try:
            result = list(sorted(self.sensor_data_custom.keys()))
        except Exception as err:
            _LOGGER.error("Other error occurred _get_types_custom: %s", err)
        return result

    # Generate waste types list, without excluded
    def _get_types_included(self):
        try:
            # result = list(sorted(set([x for x in self.types if not (x in self.exclude_list)])))
            result = list(sorted(set(self.types) - set(self.exclude_list)))
            # result = list(x for x in self.types if x not in self.exclude_list)
        except Exception as err:
            _LOGGER.error("Other error occurred _get_types_included: %s", err)
        return result

    # Generate waste data list of dicts after Today, without excluded and datetime formatted
    def _gen_data_full(self):
        try:
            result = list(
                {"type": x["type"], "date": datetime.strptime(x["date"], "%Y-%m-%d")}
                for x in self.data_raw
                if x["type"] in self.types_included
            )
        except Exception as err:
            _LOGGER.error("Other error occurred _gen_data_full: %s", err)
        return result

    # Remove history from the list of dicts before date_selected
    def _gen_data_after_date_selected(self):
        try:
            result = list(
                filter(lambda x: x["date"] >= self.date_selected, self.data_full)
            )
        except Exception as err:
            _LOGGER.error("Other error occurred _gen_data_after_date_selected: %s", err)
        return result

    ##########################################################################
    #  PROCESS WASTE DATA FROM PROVIDER - SENSOR DATA
    ##########################################################################

    # Generate sensor data for waste types, without excluded
    def _gen_provider_sensor_data(self, date):
        result = dict()
        try:
            for x in self.data_full:
                item_date = x["date"]
                item_name = x["type"]
                if item_date >= date:
                    if item_name not in result.keys():
                        if isinstance(item_date, datetime):
                            result[item_name] = item_date
                        else:
                            result[item_name] = self.default_label
            for x in self.data_full:
                item_name = x["type"]
                if item_name not in result.keys():
                    result[item_name] = self.default_label
        except Exception as err:
            _LOGGER.error("Other error occurred _gen_provider_sensor_data: %s", err)
        return result

    ##########################################################################
    #  TODAY, TOMORROW, DOT SENSOR(S)
    ##########################################################################

    def _get_day_sensor(self, date):
        result = list()
        try:
            for x in self.data_full:
                item_date = x["date"]
                item_name = x["type"]
                if item_date == date:
                    result.append(item_name)
            if not result:
                result.append(self.default_label)
        except Exception as err:
            _LOGGER.error("Other error occurred _get_day_sensor: %s", err)
        return result

    # Generate sensor data for today, tomorrow, day after tomorrow
    def _gen_day_sensor_data(self):
        result = dict()
        try:
            result["today"] = ", ".join(self.today_sensor_data)
            result["tomorrow"] = ", ".join(self.tomorrow_sensor_data)
            result["day_after_tomorrow"] = ", ".join(
                self.day_after_tomorrow_sensor_data
            )
        except Exception as err:
            _LOGGER.error("Other error occurred _gen_day_sensor_data: %s", err)
        return result

    ##########################################################################
    #  NEXT SENSOR(S)
    ##########################################################################

    # Generate sensor next_date
    def _get_next_date(self):
        result = self.default_label
        try:
            result = self.data_after_date_selected[0]["date"]
        except Exception as err:
            _LOGGER.error("Other error occurred _get_next_date: %s", err)
        return result

    # Generate sensor next_in_days
    def _get_next_in_days(self):
        result = self.default_label
        try:
            result = abs(self.today_date - self.next_date).days
        except Exception as err:
            _LOGGER.error("Other error occurred _get_next_in_days: %s", err)
        return result

    # Generate sensor next_type
    def _get_next_type(self):
        result = list()
        try:
            for x in self.data_after_date_selected:
                item_date = x["date"]
                item_name = x["type"]
                if item_date == self.next_date:
                    result.append(item_name)
            if not result:
                result.append(self.default_label)
        except Exception as err:
            _LOGGER.error("Other error occurred _get_next_type: %s", err)
        return result

    # Generate sensor data for custom sensors
    def _gen_next_sensor_data(self):
        result = dict()
        try:
            result["next_date"] = self.next_date
            result["next_type"] = ", ".join(self.next_type)
            result["next_in_days"] = self.next_in_days
        except Exception as err:
            _LOGGER.error("Other error occurred _gen_next_sensor_data: %s", err)
        return result
