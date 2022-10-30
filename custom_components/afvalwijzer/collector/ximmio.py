from datetime import datetime, timedelta

import requests

from ..const.const import _LOGGER, SENSOR_COLLECTOR_TO_URL, SENSOR_COLLECTORS_XIMMIO


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
            raise ValueError(f"Invalid provider: {self.provider}, please verify")

        collectors = ("avalex", "meerlanden", "rad", "westland")
        self.provider_url = "ximmio02" if self.provider in collectors else "ximmio01"

        TODAY = datetime.now().strftime("%d-%m-%Y")
        self.DATE_TODAY = datetime.strptime(TODAY, "%d-%m-%Y")
        self.DATE_TOMORROW = datetime.strptime(TODAY, "%d-%m-%Y") + timedelta(days=1)
        self.DATE_TODAY_NEXT_YEAR = (
            self.DATE_TODAY.date() + timedelta(days=365)
        ).strftime("%Y-%m-%d")

        self._get_waste_data_provider()

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
            item_name = "kerstbomen"
        return item_name

    def _get_waste_data_provider(self):
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
            raise ValueError(err) from err

        ##########################################################################
        # Second request: get the dates
        ##########################################################################
        try:
            url = SENSOR_COLLECTOR_TO_URL[self.provider_url][1]
            data = {
                "companyCode": companyCode,
                "startDate": self.DATE_TODAY.date(),
                "endDate": self.DATE_TODAY_NEXT_YEAR,
                "community": community,
                "uniqueAddressID": uniqueId,
            }
            raw_response = requests.post(url=url, data=data).json()
        except requests.exceptions.RequestException as err:
            raise ValueError(err) from err

        if not raw_response:
            _LOGGER.error("Address not found!")
            return

        try:
            response = raw_response["dataList"]
        except KeyError as e:
            raise KeyError(f"Invalid and/or no data received from {url}") from e

        self.waste_data_raw = []

        for item in response:
            temp = {
                "type": self.__waste_type_rename(
                    item["_pickupTypeText"].strip().lower()
                )
            }
            temp["date"] = datetime.strptime(
                sorted(item["pickupDates"])[0], "%Y-%m-%dT%H:%M:%S"
            ).strftime("%Y-%m-%d")
            self.waste_data_raw.append(temp)
