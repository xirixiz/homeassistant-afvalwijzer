from datetime import datetime

from afvalwijzer.const.const import _LOGGER, DATE_TODAY, SENSOR_COLLECTOR_TO_URL
import requests


class AfvalWijzerCollector(object):
    def __init__(
        self, provider, postal_code, street_number, suffix, default_label, exclude_list
    ):
        self.provider = provider
        self.postal_code = postal_code
        self.street_number = street_number
        self.suffix = suffix
        self.default_label = default_label
        self.exclude_list = exclude_list.strip().lower()

        collectors = (
            "mijnafvalwijzer",
            "afvalstoffendienstkalender",
            "rova",
        )
        if self.provider not in collectors:
            raise ValueError("Invalid provider: %s, please verify", self.provider)

        if self.provider == "rova":
            self.provider = "inzamelkalender.rova"

        (
            self._waste_data_raw,
            self._waste_data_with_today,
            self._waste_data_without_today,
        ) = self.get_waste_data_provider()

    def get_waste_data_provider(self):
        try:
            url = SENSOR_COLLECTOR_TO_URL["afvalwijzer_data_default"][0].format(
                self.provider,
                self.postal_code,
                self.street_number,
                self.suffix,
                datetime.today().strftime("%Y-%m-%d"),
            )
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

        try:
            waste_data_with_today = {}
            waste_data_without_today = {}

            for item in waste_data_raw:
                item_date = datetime.strptime(item["date"], "%Y-%m-%d")
                item_name = item["type"].strip().lower()
                if item_name not in self.exclude_list:
                    if item_name not in waste_data_with_today:
                        if item_date >= DATE_TODAY:
                            waste_data_with_today[item_name] = item_date

            for item in waste_data_raw:
                item_date = datetime.strptime(item["date"], "%Y-%m-%d")
                item_name = item["type"].strip().lower()
                if item_name not in self.exclude_list:
                    if item_name not in waste_data_without_today:
                        if item_date > DATE_TODAY:
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
