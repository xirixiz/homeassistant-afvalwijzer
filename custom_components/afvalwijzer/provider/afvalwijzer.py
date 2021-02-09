from datetime import datetime, timedelta

import requests

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
        self.exclude_list = exclude_list

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
        self.today_to_tomorrow = datetime.strptime(self.today, "%d-%m-%Y") + timedelta(
            days=1
        )
        self.tomorrow = datetime.strftime(self.today_to_tomorrow, "%d-%m-%Y")
        self.tomorrow_date = datetime.strptime(self.tomorrow, "%d-%m-%Y")

        # day after tomorow
        self.today_to_day_after_tomorrow = datetime.strptime(
            self.today, "%d-%m-%Y"
        ) + timedelta(days=2)
        self.day_after_tomorrow = datetime.strftime(
            self.today_to_day_after_tomorrow, "%d-%m-%Y"
        )
        self.day_after_tomorrow_date = datetime.strptime(
            self.day_after_tomorrow, "%d-%m-%Y"
        )

        # data collect
        (
            self._waste_data_with_today,
            self._waste_data_without_today,
        ) = self.get_waste_data_provider()
        self._waste_data_custom = self.get_waste_data_custom()
        self._waste_types_provider = self.get_waste_types_provider()
        self._waste_types_custom = self.get_waste_types_custom()

    ##########################################################################
    #  GET WASTE DATA FROM PROVIDER
    ##########################################################################

    def get_waste_data_provider(self):
        try:
            _LOGGER.debug(
                "Connecting to the frontend (json data) of: %s", self.provider
            )

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
                json_data = (
                    json_response["ophaaldagen"]["data"]
                    + json_response["ophaaldagenNext"]["data"]
                )
            except ValueError:
                raise ValueError("Invalid JSON data received from " + url)

            waste_data_with_today = {}
            waste_data_without_today = {}

            for item in json_data:
                item_date = datetime.strptime(item["date"], "%Y-%m-%d")
                item_name = item["type"]
                if item_name.strip().lower() not in self.exclude_list:
                    if item_name not in waste_data_with_today:
                        if item_date >= self.today_date:
                            waste_data_with_today[item_name] = item_date

            for item in json_data:
                item_date = datetime.strptime(item["date"], "%Y-%m-%d")
                item_name = item["type"]
                if item_name.strip().lower() not in self.exclude_list:
                    if item_name not in waste_data_without_today:
                        if item_date > self.today_date:
                            waste_data_without_today[item_name] = item_date

            try:
                for item in json_data:
                    item_name = item["type"]
                    if item_name.strip().lower() not in self.exclude_list:
                        if item_name not in waste_data_with_today.keys():
                            waste_data_with_today[item_name] = self.default_label
                        if item_name not in waste_data_without_today.keys():
                            waste_data_without_today[item_name] = self.default_label
            except Exception as err:
                _LOGGER.error("Other error occurred: %s", err)

            return waste_data_with_today, waste_data_without_today

        except Exception as err:
            _LOGGER.error("Other error occurred: %s", err)

    ##########################################################################
    #  GENERATE DATA FOR CUSTOM SENSORS
    ##########################################################################
    def get_waste_data_custom(self):

        # start counting wihth Today's date or with Tomorrow"s date
        if self.include_date_today.casefold() in ("true", "yes"):
            date_selected = self.today_date
        else:
            date_selected = self.tomorrow_date

        waste_data_provider = self._waste_data_with_today
        waste_data_custom = {}
        today_multiple_items = []
        tomorrow_multiple_items = []
        day_after_tomorrow_multiple_items = []
        next_item_multiple_items = []

        ##########################################################################
        #  GENERATE TODAY, TOMORROW, DAY AFTER TOMORROW SENSOR DATA
        ##########################################################################
        try:
            waste_data_temp = {
                key: value
                for key, value in waste_data_provider.items()
                if isinstance(value, datetime)
            }

            for key, value in waste_data_temp.items():
                # waste type(s) today
                if value == self.today_date:
                    if "today" in waste_data_custom.keys():
                        today_multiple_items.append(key)
                        waste_data_custom["today"] = ", ".join(today_multiple_items)
                    else:
                        today_multiple_items.append(key)
                        waste_data_custom["today"] = key
                # waste type(s) tomorrow
                if value == self.tomorrow_date:
                    if "tomorrow" in waste_data_custom.keys():
                        tomorrow_multiple_items.append(key)
                        waste_data_custom["tomorrow"] = ", ".join(
                            tomorrow_multiple_items
                        )
                    else:
                        tomorrow_multiple_items.append(key)
                        waste_data_custom["tomorrow"] = key
                # waste type(s) day_after_tomorrow
                if value == self.day_after_tomorrow_date:
                    if "day_after_tomorrow" in waste_data_custom.keys():
                        day_after_tomorrow_multiple_items.append(key)
                        waste_data_custom["day_after_tomorrow"] = ", ".join(
                            day_after_tomorrow_multiple_items
                        )
                    else:
                        day_after_tomorrow_multiple_items.append(key)
                        waste_data_custom["day_after_tomorrow"] = key

            # set value to none if no value has been found
            if "today" not in waste_data_custom.keys():
                waste_data_custom["today"] = self.default_label
            if "tomorrow" not in waste_data_custom.keys():
                waste_data_custom["tomorrow"] = self.default_label
            if "day_after_tomorrow" not in waste_data_custom.keys():
                waste_data_custom["day_after_tomorrow"] = self.default_label

        except Exception as err:
            _LOGGER.error("Error occurred: %s", err)

        ##########################################################################
        #  GENERATE NEXT_ SENSOR DATA
        ##########################################################################

        try:
            waste_data_temp = {
                key: value
                for key, value in waste_data_provider.items()
                if isinstance(value, datetime) and value >= date_selected
            }

            # first upcoming pickup date of any waste type
            waste_data_custom["next_date"] = min(waste_data_temp.values())

            # first upcoming waste type pickup in days
            waste_data_custom["next_in_days"] = abs(
                (self.today_date - min(waste_data_temp.values())).days
            )

            # first upcoming waste type(s) pickup
            upcoming_waste_date = min(waste_data_temp.values())

            for key, value in waste_data_temp.items():
                if value == upcoming_waste_date:
                    if "next_item" in waste_data_custom.keys():
                        next_item_multiple_items.append(key)
                        waste_data_custom["next_item"] = ", ".join(
                            next_item_multiple_items
                        )
                    else:
                        next_item_multiple_items.append(key)
                        waste_data_custom["next_item"] = key

            # set value to none if no value has been found
            if "next_date" not in waste_data_custom.keys():
                waste_data_custom["next_date"] = self.default_label
            if "next_in_days" not in waste_data_custom.keys():
                waste_data_custom["next_in_days"] = self.default_label
            if "next_item" not in waste_data_custom.keys():
                waste_data_custom["next_item"] = self.default_label

        except Exception as err:
            _LOGGER.error("Error occurred: %s", err)

        return waste_data_custom

    ##########################################################################
    #  GENERATE WASTE TYPES LIST FROM PROVIDER
    ##########################################################################

    def get_waste_types_provider(self):
        waste_data_provider = self._waste_data_without_today
        waste_list_provider = list(waste_data_provider.keys())
        return waste_list_provider

    ##########################################################################
    #  GENERATE SENSOR TYPES LIST FOR CUSTOM SENSORS
    ##########################################################################

    def get_waste_types_custom(self):
        waste_data_custom = self._waste_data_custom
        waste_list_custom = list(waste_data_custom.keys())
        return waste_list_custom

    ##########################################################################
    #  PROPERTIES FOR EXECUTION
    ##########################################################################

    @property
    def waste_data_with_today(self):
        return self._waste_data_with_today

    @property
    def waste_data_without_today(self):
        return self._waste_data_without_today

    @property
    def waste_data_custom(self):
        return self._waste_data_custom

    @property
    def waste_types_provider(self):
        return self._waste_types_provider

    @property
    def waste_types_custom(self):
        return self._waste_types_custom
