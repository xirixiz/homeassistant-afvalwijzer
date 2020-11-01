from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

from ..const.const import _LOGGER, MONTH_TO_NUMBER, SENSOR_PROVIDER_TO_URL


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
    ):
        self.provider = provider
        self.postal_code = postal_code
        self.street_number = street_number
        self.suffix = suffix
        self.include_date_today = include_date_today
        self.default_label = default_label

        _providers = ("mijnafvalwijzer", "afvalstoffendienstkalender", "rova")
        if self.provider not in _providers:
            print("Invalid provider: %s, please verify", self.provider)

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
    #  DATE CALCULATION FUNCTION
    ##########################################################################

    def calculate_days_between_dates(self, start, end):
        try:
            start_date = datetime.strptime(start, "%d-%m-%Y")
            end_date = datetime.strptime(end, "%d-%m-%Y")
            return abs((end_date - start_date).days)
        except ValueError:
            _LOGGER.error("Something went wrong calculating days between dates.")

    ##########################################################################
    #  GET WASTE DATA FROM PROVIDER
    ##########################################################################

    def get_waste_data_provider(self):
        try:
            _LOGGER.debug(
                "Connecting to the frontend (scrape data) of: %s", self.provider
            )
            if self.provider == "rova":
                url = SENSOR_PROVIDER_TO_URL["afvalwijzer_scraper_rova"][0].format(
                    self.provider, self.postal_code, self.street_number, self.suffix
                )
            else:
                url = SENSOR_PROVIDER_TO_URL["afvalwijzer_scraper_default"][0].format(
                    self.provider, self.postal_code, self.street_number, self.suffix
                )
            _LOGGER.debug("URL parsed: %s", url)

            # get scraper data
            response = requests.get(url)
            response.raise_for_status()
            html = response.text
            soup = BeautifulSoup(html, "html.parser")
            jaaroverzicht = soup.select('a[href*="#waste"] p[class]')
            jaartal = soup.find("div", {"class": "ophaaldagen"})["id"].strip("jaar-")

            #_LOGGER.debug("Jaaroverzicht %s", jaaroverzicht)
            _LOGGER.debug("Year %s", jaartal)

            waste_data_with_today = {}
            waste_data_without_today = {}

            # get waste data from provider
            try:
                for item in jaaroverzicht:
                    for x in item["class"]:
                        waste_item = x
                        waste_date = item.find(
                            "span", {"class": "span-line-break"}
                        )
                        # when there is no span with class span-line-break, just use date
                        if waste_date is None:
                            waste_date = str(item).split(">")[1]
                            waste_date = waste_date.split("<")[0]
                        else:
                            waste_date = waste_date.string.strip()

                        # convert month to month number by splitting the waste_date value
                        split_waste_date = waste_date.split(" ")
                        day = split_waste_date[1]
                        month = MONTH_TO_NUMBER[split_waste_date[2]]
                        waste_date_formatted = datetime.strptime(
                            day + "-" + month + "-" + jaartal, "%d-%m-%Y"
                        )
                        # create waste data with today
                        if waste_date_formatted >= self.today_date:
                            if waste_item not in waste_data_with_today.keys():
                                waste_data_with_today[
                                    waste_item
                                ] = waste_date_formatted.strftime("%d-%m-%Y")
                        # create waste data without today
                        if waste_date_formatted > self.today_date:
                            if waste_item not in waste_data_without_today.keys():
                                waste_data_without_today[
                                    waste_item
                                ] = waste_date_formatted.strftime("%d-%m-%Y")
            except Exception as err:
                _LOGGER.error("Other error occurred: %s", err)

            try:
                for item in jaaroverzicht:
                    for x in item["class"]:
                        waste_item = x
                        if waste_item not in waste_data_with_today.keys():
                            waste_data_with_today[waste_item] = self.default_label
                        if waste_item not in waste_data_without_today.keys():
                            waste_data_without_today[waste_item] = self.default_label
            except Exception as err:
                _LOGGER.error("Other error occurred: %s", err)

            _LOGGER.debug(
                "Generating waste_data_with_today = %s", waste_data_with_today
            )
            _LOGGER.debug(
                "Generating waste_data_without_today = %s", waste_data_without_today
            )
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
                if len(value) != 0
            }
            _LOGGER.debug(
                "waste_data_temp for today, tomorrow and day after tomorrow  %s",
                waste_data_temp,
            )
            for key, value in waste_data_temp.items():
                # waste type(s) today
                if value == self.today:
                    if "today" in waste_data_custom.keys():
                        today_multiple_items.append(key)
                        waste_data_custom["today"] = ", ".join(today_multiple_items)
                    else:
                        today_multiple_items.append(key)
                        waste_data_custom["today"] = key
                # waste type(s) tomorrow
                if value == self.tomorrow:
                    if "tomorrow" in waste_data_custom.keys():
                        tomorrow_multiple_items.append(key)
                        waste_data_custom["tomorrow"] = ", ".join(
                            tomorrow_multiple_items
                        )
                    else:
                        tomorrow_multiple_items.append(key)
                        waste_data_custom["tomorrow"] = key
                # waste type(s) day_after_tomorrow
                if value == self.day_after_tomorrow:
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
                if len(value) != 0
                and value != self.default_label
                and datetime.strptime(value, "%d-%m-%Y") >= date_selected
            }
            _LOGGER.debug("waste_data_temp for next_ %s", waste_data_temp)

            # first upcoming pickup date of any waste type
            waste_data_custom["next_date"] = datetime.strptime(
                min(waste_data_temp.values()), "%d-%m-%Y"
            ).strftime("%d-%m-%Y")

            # first upcoming waste type pickup in days
            waste_data_custom["next_in_days"] = self.calculate_days_between_dates(
                self.today, min(waste_data_temp.values())
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

        _LOGGER.debug("Generating waste_data_custom = %s", waste_data_custom)

        return waste_data_custom

    ##########################################################################
    #  GENERATE WASTE TYPES LIST FROM PROVIDER
    ##########################################################################

    def get_waste_types_provider(self):
        waste_data_provider = self._waste_data_without_today
        waste_list_provider = list(waste_data_provider.keys())
        _LOGGER.debug("Generating waste_data_provider = %s", waste_data_provider)
        _LOGGER.debug("Generating waste_list_provider = %s", waste_list_provider)

        return waste_list_provider

    ##########################################################################
    #  GENERATE SENSOR TYPES LIST FOR CUSTOM SENSORS
    ##########################################################################

    def get_waste_types_custom(self):
        waste_data_custom = self._waste_data_custom
        waste_list_custom = list(waste_data_custom.keys())
        _LOGGER.debug("Generating waste_data_custom = %s", waste_data_custom)
        _LOGGER.debug("Generating waste_list_custom = %s", waste_list_custom)

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
