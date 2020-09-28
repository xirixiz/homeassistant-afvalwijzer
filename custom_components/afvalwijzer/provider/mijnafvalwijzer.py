import json
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError

from ..const.const import _LOGGER, MONTH_TO_NUMBER, SENSOR_PROVIDER_TO_URL


class MijnAfvalWijzer(object):
    def __init__(
        self,
        provider,
        api_token,
        postal_code,
        street_number,
        suffix,
        include_date_today,
        default_label,
    ):
        self.provider = provider
        self.api_token = api_token
        self.postal_code = postal_code
        self.street_number = street_number
        self.suffix = suffix
        self.include_date_today = include_date_today
        self.default_label = default_label

        _providers = ("mijnafvalwijzer", "afvalstoffendienstkalender")
        if self.provider not in _providers:
            print("Invalid provider: {}, please verify".format(self.provider))
        # date today
        self.today = datetime.today().strftime("%Y-%m-%d")
        # date tomorrow
        today_to_tomorrow = datetime.strptime(self.today, "%Y-%m-%d") + timedelta(
            days=1
        )
        self.tomorrow = datetime.strftime(today_to_tomorrow, "%Y-%m-%d")
        # date day_after_tomorrow
        today_to_day_after_tomorrow = datetime.strptime(
            self.today, "%Y-%m-%d"
        ) + timedelta(days=2)
        self.day_after_tomorrow = datetime.strftime(
            today_to_day_after_tomorrow, "%Y-%m-%d"
        )
        # start counting wihth Today's date or with Tomorrow"s date
        if self.include_date_today.casefold() in ("true", "yes"):
            self.date_selected = self.today
        else:
            self.date_selected = self.tomorrow
        # data collector functions
        self._waste_data_provider = self.get_waste_data_provider()
        self._waste_data_custom = self.get_waste_data_custom()
        self._waste_types_provider = self.get_waste_types_provider()
        self._waste_types_custom = self.get_waste_types_custom()

    def calculate_days_between_dates(self, start, end):
        try:
            start_date = datetime.strptime(start, "%Y-%m-%d")
            end_date = datetime.strptime(end, "%Y-%m-%d")
            return abs((end_date - start_date).days)
        except ValueError:
            _LOGGER.error("Something went wrong calculating days between dates.")
            return False

    def get_date_from_waste_type(self, html, waste_type):
        try:
            results = html.findAll("p", {"class": waste_type})

            for result in results:
                date = result.find("span", {"class": "span-line-break"})

                # Sometimes there is no span with class span-line-break, so we just get the result as date
                if date is None:
                    date = str(result).split(">")[1]
                    date = date.split("<")[0]
                else:
                    # get the value of the span
                    date = date.string
                day = date.split()[1]
                month = MONTH_TO_NUMBER[date.split()[2]]
                # the year is always this year because it's a 'jaaroverzicht'
                year = datetime.today().year

                if int(month) >= datetime.today().month:
                    if int(month) == datetime.today().month:
                        if int(day) >= datetime.today().day:
                            return str(year) + "-" + str(month) + "-" + str(day)
                    else:
                        return str(year) + "-" + str(month) + "-" + str(day)
            # if nothing was found
            return ""
        except Exception as err:
            _LOGGER.warning("Something went wrong while splitting data: %s.", err)
            return ""

    def get_waste_data_provider(self):
        try:
            ########## API WASTE DICTIONARY ##########
            if len(self.api_token) != 0:
                _LOGGER.debug("Connecting to the backend (api) of: %s", self.provider)
                url = SENSOR_PROVIDER_TO_URL["mijnafvalwijzer_api"][0].format(
                    self.provider,
                    self.api_token,
                    self.postal_code,
                    self.street_number,
                    self.suffix,
                    self.today,
                )
                _LOGGER.debug("URL parsed: %s", url)

                # get json data
                response = requests.get(url)
                response.raise_for_status()
                json_response = response.json()
                json_data = (
                    json_response["ophaaldagen"]["data"]
                    + json_response["ophaaldagenNext"]["data"]
                )

                # create a dictionary for every upcoming unique waste item, together with the first upcoming pickup date
                waste_dict_provider = {}
                for item in json_data:
                    if item["type"] not in waste_dict_provider.keys():
                        if item["date"] >= self.today:
                            waste_dict_provider[item["type"]] = item["date"]
                for item in json_data:
                    if item["date"] <= self.today:
                        if item["type"] not in waste_dict_provider.keys():
                            waste_dict_provider[item["type"]] = self.default_label
                return waste_dict_provider
            ########## BEGIN SCRAPER WASTE DICTIONARY ##########
            if len(self.api_token) == 0:
                _LOGGER.debug(
                    "Connecting to the frontend (scrape data) of: %s", self.provider
                )
                url = SENSOR_PROVIDER_TO_URL["mijnafvalwijzer_scraper"][0].format(
                    self.provider, self.postal_code, self.street_number, self.suffix
                )
                _LOGGER.debug("URL parsed: %s", url)

                # get scraper data
                response = requests.get(url)
                response.raise_for_status()
                html = response.text
                soup = BeautifulSoup(html, "html.parser")
                jaaroverzicht = soup.find(id="jaaroverzicht")
                jaaroverzicht_waste_types = jaaroverzicht.findAll("p")

                waste_dict_provider = {}
                try:
                    for waste_type in jaaroverzicht_waste_types:
                        if waste_type not in waste_dict_provider.keys():
                            waste_dict_provider[waste_type["class"][0]] = ""
                except KeyError:
                    pass
                for waste_type in waste_dict_provider.keys():
                    waste_dict_provider[waste_type] = self.get_date_from_waste_type(
                        jaaroverzicht, waste_type
                    )
                # set value to none if no value has been found
                for key in waste_dict_provider.keys():
                    if len(waste_dict_provider[key]) == 0:
                        waste_dict_provider[key] = self.default_label
                return waste_dict_provider
        except HTTPError as http_err:
            _LOGGER.error("HTTP error occurred: %s", http_err)
            return False
        except Exception as err:
            _LOGGER.error("Other error occurred: %s", err)
            return False

    def get_waste_data_custom(self):
        waste_dict_provider = self._waste_data_provider
        waste_dict_custom = {}
        today_multiple_items = []
        tomorrow_multiple_items = []
        day_after_tomorrow_multiple_items = []
        first_next_item_multiple_items = []
        waste_dict_temp = {
            key: value for key, value in waste_dict_provider.items() if len(value) != 0
        }

        try:
            for key, value in waste_dict_temp.items():
                # waste type(s) today
                if value == self.today:
                    if "today" in waste_dict_custom.keys():
                        today_multiple_items.append(key)
                        waste_dict_custom["today"] = ", ".join(today_multiple_items)
                    else:
                        today_multiple_items.append(key)
                        waste_dict_custom["today"] = key
                # waste type(s) tomorrow
                if value == self.tomorrow:
                    if "tomorrow" in waste_dict_custom.keys():
                        tomorrow_multiple_items.append(key)
                        waste_dict_custom["tomorrow"] = ", ".join(
                            tomorrow_multiple_items
                        )
                    else:
                        tomorrow_multiple_items.append(key)
                        waste_dict_custom["tomorrow"] = key
                # waste type(s) day_after_tomorrow
                if value == self.day_after_tomorrow:
                    if "day_after_tomorrow" in waste_dict_custom.keys():
                        day_after_tomorrow_multiple_items.append(key)
                        waste_dict_custom["day_after_tomorrow"] = ", ".join(
                            day_after_tomorrow_multiple_items
                        )
                    else:
                        day_after_tomorrow_multiple_items.append(key)
                        waste_dict_custom["day_after_tomorrow"] = key
            # set value to none if no value has been found
            if "today" not in waste_dict_custom.keys():
                waste_dict_custom["today"] = self.default_label
            if "tomorrow" not in waste_dict_custom.keys():
                waste_dict_custom["tomorrow"] = self.default_label
            if "day_after_tomorrow" not in waste_dict_custom.keys():
                waste_dict_custom["day_after_tomorrow"] = self.default_label
        except Exception as err:
            _LOGGER.error("Error occurred: %s", err)
            return False
        try:
            # create a temporary dictionary for the first_next_* items as the output is dependent on either to take today into account or not
            waste_dict_temp_date_selected = {
                key: value
                for key, value in waste_dict_provider.items()
                if len(value) != 0
                and value != self.default_label
                and value >= self.date_selected
            }
            # first upcoming pickup date of any waste type
            waste_dict_custom["first_next_date"] = datetime.strptime(
                min(waste_dict_temp_date_selected.values()), "%Y-%m-%d"
            ).strftime("%d-%m-%Y")
            # first upcoming waste type pickup in days
            waste_dict_custom["first_next_in_days"] = self.calculate_days_between_dates(
                self.today, min(waste_dict_temp_date_selected.values())
            )
            # first upcoming waste type(s) pickup
            first_upcoming_wate_date = min(waste_dict_temp_date_selected.values())

            for key, value in waste_dict_temp_date_selected.items():
                if value == first_upcoming_wate_date:
                    if "first_next_item" in waste_dict_custom.keys():
                        first_next_item_multiple_items.append(key)
                        waste_dict_custom["first_next_item"] = ", ".join(
                            first_next_item_multiple_items
                        )
                    else:
                        first_next_item_multiple_items.append(key)
                        waste_dict_custom["first_next_item"] = key
            # set value to none if no value has been found
            if "first_next_date" not in waste_dict_custom.keys():
                waste_dict_custom["first_next_date"] = self.default_label
            if "first_next_in_days" not in waste_dict_custom.keys():
                waste_dict_custom["first_next_in_days"] = self.default_label
            if "first_next_item" not in waste_dict_custom.keys():
                waste_dict_custom["first_next_item"] = self.default_label
        except Exception as err:
            _LOGGER.error("Error occurred: %s", err)
            return False
        try:
            # date format to Dutch standard for waste_dict_provider
            for key, value in waste_dict_provider.items():
                if value != 0 and value != self.default_label:
                    waste_dict_provider[key] = datetime.strptime(
                        value, "%Y-%m-%d"
                    ).strftime("%d-%m-%Y")
        except Exception as err:
            _LOGGER.error("Error occurred: %s", err)
            return False
        return waste_dict_custom

    def get_waste_types_provider(self):
        waste_dict_provider = self._waste_data_provider
        waste_list_provider = list(waste_dict_provider.keys())
        _LOGGER.debug("Generating waste_dict_provider = %s", waste_dict_provider)
        _LOGGER.debug("Generating waste_list_provider = %s", waste_list_provider)

        return waste_list_provider

    def get_waste_types_custom(self):
        _LOGGER.debug("Generating key list from custom waste types")
        waste_dict_custom = self._waste_data_custom
        waste_list_custom = list(waste_dict_custom.keys())
        _LOGGER.debug("Generating waste_dict_custom = %s", waste_dict_custom)
        _LOGGER.debug("Generating waste_list_custom = %s", waste_list_custom)

        return waste_list_custom

    @property
    def waste_data_provider(self):
        return self._waste_data_provider

    @property
    def waste_data_custom(self):
        return self._waste_data_custom

    @property
    def waste_types_provider(self):
        return self._waste_types_provider

    @property
    def waste_types_custom(self):
        return self._waste_types_custom
