from datetime import datetime, timedelta

from afvalwijzer.const.const import (
    _LOGGER,
    DATE_TODAY,
    DATE_TODAY_NEXT_YEAR,
    SENSOR_COLLECTORS_XIMMIO,
    SENSOR_COLLECTOR_TO_URL,
)
# from dateutil.relativedelta import relativedelta
import requests


class XimmioCollector(object):
    def __init__(
        self, provider, postal_code, street_number, suffix, default_label, exclude_list
    ):
        self.provider = provider
        self.postal_code = postal_code
        self.street_number = street_number
        self.suffix = suffix
        self.default_label = default_label
        self.exclude_list = exclude_list.strip().lower()

        if self.provider not in SENSOR_COLLECTORS_XIMMIO.keys():
            raise ValueError("Invalid provider: %s, please verify", self.provider)

        _providers = ("avalex", "meerlanden", "rad", "westland")
        if self.provider in _providers:
            self.provider_url = "ximmio02"
        else:
            self.provider_url = "ximmio01"

        (   self._waste_data_raw,
            self._waste_data_with_today,
            self._waste_data_without_today,
        ) = self.get_waste_data_provider()


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
                temp["type"] = self.__waste_type_rename(item["_pickupTypeText"].strip().lower())
                temp["date"] = datetime.strptime(item["pickupDates"][0], "%Y-%m-%dT%H:%M:%S")
                waste_data_raw_formatted.append(temp)

            for item in waste_data_raw_formatted:
                item_date = item["date"]
                item_name = item["type"]
                if item_name not in self.exclude_list:
                    if item_name not in waste_data_with_today:
                        if item_date >= DATE_TODAY:
                            waste_data_with_today[item_name] = item_date

            for item in waste_data_raw_formatted:
                item_date = item["date"]
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

            return waste_data_raw_formatted, waste_data_with_today, waste_data_without_today
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
