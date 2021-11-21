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
        self.exclude_list = exclude_list.split(',')
        self.exclude_list = [item.strip().lower() for item in self.exclude_list]

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

        # today
        self.today = datetime.today().strftime("%d-%m-%Y")
        self.today_date = datetime.strptime(self.today, "%d-%m-%Y")

        # tomorow
        self.today_to_tomorrow = datetime.strptime(self.today, "%d-%m-%Y") + timedelta(days=1)
        self.tomorrow = datetime.strftime(self.today_to_tomorrow, "%d-%m-%Y")
        self.tomorrow_date = datetime.strptime(self.tomorrow, "%d-%m-%Y")

        # day after tomorow
        self.today_to_day_after_tomorrow = datetime.strptime(self.today, "%d-%m-%Y") + timedelta(days=2)
        self.day_after_tomorrow = datetime.strftime(self.today_to_day_after_tomorrow, "%d-%m-%Y")
        self.day_after_tomorrow_date = datetime.strptime(self.day_after_tomorrow, "%d-%m-%Y")

        if self.include_date_today.casefold() in ("true", "yes"):
            self.date_selected = self.today_date
        else:
            self.date_selected = self.tomorrow_date

        ##########################################################################
        #  DEVELOPMENT MODE
        ##########################################################################

        self.development_mode = True
        if self.development_mode:
            print("##### DEVELOPMENT MODE #####")

        ##########################################################################
        #  GET AND GENERATE DATA
        ##########################################################################

        # Get data list of dicts from provider
        self.data_raw = self._get_waste_data_provider()
        # Generate waste types list
        self.waste_types = self._get_waste_types()
        # Generate waste types list, without excluded
        self.waste_types_exluded_removed = self._get_waste_types_exluded_removed()
        # Generate waste data list of dicts after Today, without excluded and datetime formatted
        self.waste_data = self._gen_waste_list_full()
        # Get next waste date
        self.next_date = self._get_next_date()
        # Get next waste date in days
        self.next_in_days = self._get_next_in_days()

    # for item in waste_data_provider_past_removed:
    #     item_date = datetime.strptime(item["date"], "%Y-%m-%d")
    #     item_name = item["type"].strip().lower()
    #     if item_date == waste_data_provider_next_date:
    #         if "next_item" in waste_data_custom.keys():
    #             if item_name not in waste_data_custom.keys():
    #                 next_item_multiple_items.append(item_name)
    #                 waste_data_custom["next_item"] = ", ".join(
    #                     next_item_multiple_items
    #                 )
    #         else:
    #             next_item_multiple_items.append(item_name)
    #             waste_data_custom["next_item"] = item_name

    # # set value to none if no value has been found
    # if "next_date" not in waste_data_custom.keys():
    #     waste_data_custom["next_date"] = self.default_label
    # if "next_in_days" not in waste_data_custom.keys():
    #     waste_data_custom["next_in_days"] = self.default_label
    # if "next_item" not in waste_data_custom.keys():
    #     waste_data_custom["next_item"] = self.default_label

        ##########################################################################
        #  GENERATE SENSOR DATA
        ##########################################################################
        self.provider_sensor_data = self._gen_provider_sensor_data()
        self.provider_waste_types = self.waste_types_exluded_removed

    ##########################################################################
    #  GET DATA LISTS OF DICTS FROM PROVIDER
    ##########################################################################

    def _get_waste_data_provider(self):
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
                    result = (json_response["ophaaldagen"]["data"] + json_response["ophaaldagenNext"]["data"])
                except ValueError:
                    raise ValueError("Invalid and/or no JSON data received from " + url)

                if not result:
                    _LOGGER.error("No waste data found!")
                    return
            else:
                result = [{'nameType': 'pmd', 'type': 'pmd', 'date': '2021-01-06'}, {'nameType': 'kerstbomen', 'type': 'kerstbomen', 'date': '2021-01-09'}, {'nameType': 'papier', 'type': 'papier', 'date': '2021-01-09'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-01-11'}, {'nameType': 'restafval', 'type': 'restafval', 'date': '2021-01-18'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-01-20'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-01-25'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-02-03'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-02-08'}, {'nameType': 'papier', 'type': 'papier', 'date': '2021-02-13'}, {'nameType': 'restafval', 'type': 'restafval', 'date': '2021-02-15'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-02-17'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-02-22'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-03-03'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-03-08'}, {'nameType': 'papier', 'type': 'papier', 'date': '2021-03-13'}, {'nameType': 'restafval', 'type': 'restafval', 'date': '2021-03-15'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-03-17'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-03-22'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-03-31'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-04-09'}, {'nameType': 'papier', 'type': 'papier', 'date': '2021-04-10'}, {'nameType': 'restafval', 'type': 'restafval', 'date': '2021-04-12'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-04-14'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-04-19'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-04-28'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-05-03'}, {'nameType': 'papier', 'type': 'papier', 'date': '2021-05-08'}, {'nameType': 'restafval', 'type': 'restafval', 'date': '2021-05-10'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-05-12'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-05-17'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-05-26'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-05-31'}, {'nameType': 'restafval', 'type': 'restafval', 'date': '2021-06-07'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-06-09'}, {'nameType': 'papier', 'type': 'papier', 'date': '2021-06-12'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-06-14'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-06-23'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-06-28'}, {'nameType': 'restafval', 'type': 'restafval', 'date': '2021-07-05'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-07-07'}, {'nameType': 'papier', 'type': 'papier', 'date': '2021-07-10'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-07-12'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-07-21'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-07-26'}, {'nameType': 'restafval', 'type': 'restafval', 'date': '2021-08-02'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-08-04'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-08-09'}, {'nameType': 'papier', 'type': 'papier', 'date': '2021-08-14'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-08-18'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-08-23'}, {'nameType': 'restafval', 'type': 'restafval', 'date': '2021-08-30'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-09-01'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-09-06'}, {'nameType': 'papier', 'type': 'papier', 'date': '2021-09-11'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-09-15'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-09-20'}, {'nameType': 'restafval', 'type': 'restafval', 'date': '2021-09-27'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-09-29'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-10-04'}, {'nameType': 'papier', 'type': 'papier', 'date': '2021-10-09'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-10-13'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-10-18'}, {'nameType': 'restafval', 'type': 'restafval', 'date': '2021-10-25'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-10-27'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-11-01'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-11-10'}, {'nameType': 'papier', 'type': 'papier', 'date': '2021-11-13'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-11-15'}, {'nameType': 'restafval', 'type': 'restafval', 'date': '2021-11-22'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-11-24'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-11-29'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-12-08'}, {'nameType': 'papier', 'type': 'papier', 'date': '2021-12-11'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-12-13'}, {'nameType': 'restafval', 'type': 'restafval', 'date': '2021-12-20'}, {'nameType': 'pmd', 'type': 'pmd', 'date': '2021-12-22'}, {'nameType': 'gft', 'type': 'gft', 'date': '2021-12-27'}]
                result = [{k.strip().lower(): v for k, v in x.items()} for x in result]

        except Exception as err:
            _LOGGER.error("Other error occurred _get_waste_data_provider: %s", err)

        return result

    ##########################################################################
    #  PROCESS WASTE DATA FROM PROVIDER
    ##########################################################################

    # Generate waste types list
    def _get_waste_types(self):
        try:
            result = list(sorted(set([x['type'] for x in self.data_raw])))
        except Exception as err:
            _LOGGER.error("Other error occurred _get_waste_types: %s", err)
        return result

    # Generate waste types list, without excluded
    def _get_waste_types_exluded_removed(self):
        try:
            result = list(sorted(set([x for x in self.waste_types if not (x in self.exclude_list)])))
            # result = list(sorted(set(self.waste_types) - set(self.exclude_list)))
            # result = [x for x in self.waste_types if x not in self.exclude_list]
        except Exception as err:
            _LOGGER.error("Other error occurred _get_waste_types_exluded_removed: %s", err)
        return result

    # Generate waste data list of dicts after Today, without excluded and datetime formatted
    def _gen_waste_list_full(self):
        try:
            result = [{"type": x['type'], "date": x['date']} for x in self.data_raw if x['type'] in self.waste_types_exluded_removed]
            result = self.__remove_history(result)
            result = self.__convert_to_datetime(result)
        except Exception as err:
            _LOGGER.error("Other error occurred _gen_waste_list_full: %s", err)
        return result

    # Remove history from the list of dicts before date_selected
    def __remove_history(self, data):
        try:
            result = list(filter(lambda item: datetime.strptime(item["date"], "%Y-%m-%d") >= self.date_selected, data))
        except Exception as err:
            _LOGGER.error("Other error occurred __remove_history: %s", err)
        return result

    # Convert date stings to datetime
    def __convert_to_datetime(self, data):
        try:
            for item in data:
                item["date"] = datetime.strptime(item["date"], "%Y-%m-%d")
        except Exception as err:
            _LOGGER.error("Other error occurred __convert_to_datetime: %s", err)
        return data

    # Generate sensor data for waste types, without excluded
    def _gen_provider_sensor_data(self):
        result = dict()
        try:
            for item in self.waste_data:
                item_date = item["date"]
                item_name = item["type"]
                if item_date >= self.date_selected:
                    if item_name not in result:
                        if isinstance(item_date, datetime):
                            result[item_name] = item_date
                        else:
                            result[item_name] = self.default_label
        except Exception as err:
            _LOGGER.error("Other error occurred _gen_provider_sensor_data: %s", err)
        return result

    # def _gen_provider_sensor_data(self):
    #     result = list()
    #     try:
    #         for item in self.waste_data:
    #             data_temp = dict()
    #             item_date = item["date"]
    #             item_name = item["type"]
    #             if item_date >= self.date_selected:
    #                 if not any(x['type'] == item_name for x in result):
    #                     data_temp['type'] = item_name
    #                     if isinstance(item_date, datetime):
    #                         data_temp['date'] = item_date
    #                     else:
    #                         data_temp['date'] = self.default_label
    #                     result.append(data_temp)
    #         result.append(self.__gen_sensor_data_none(result))
    #     except Exception as err:
    #         _LOGGER.error("Other error occurred _gen_provider_sensor_data: %s", err)
    #     return result

    # Generate sensor data for custom sensors
    def _gen_custom_sensor_data(self, data):
        result = list()
        try:
            result.append(data_temp)
            result.append(self.__gen_sensor_data_none(result))
        except Exception as err:
            _LOGGER.error("Other error occurred _gen_custom_sensor_data: %s", err)
        return result

    # Generate sensor data waste types without date. Set default_label.
    def __gen_sensor_data_none(self, data):
        result = list()
        try:
            for item_name in self.waste_types_exluded_removed:
                data_temp = dict()
                if not any(item['type'] == item_name for item in data):
                    data_temp['type'] = item_name
                    data_temp['date'] = self.default_label
                    result.append(data_temp)
        except Exception as err:
            _LOGGER.error("Other error occurred __gen_sensor_data_none: %s", err)
        return result

    # Generate sensor next_date
    def _get_next_date(self):
        try:
            result = self.waste_data[0]["date"]
        except Exception as err:
            _LOGGER.error("Other error occurred _get_next_date: %s", err)
        return result

    # Generate sensor next_in_days
    def _get_next_in_days(self):
        try:
            result = abs(self.today_date - self.next_date).days
        except Exception as err:
            _LOGGER.error("Other error occurred _get_next_in_days: %s", err)
        return result

    ##########################################################################
    #  PROPERTIES FOR EXECUTION
    ##########################################################################

    @ property
    def result(self):
        return self._provider_sensor_data

    @ property
    def result(self):
        return self.provider_waste_types
