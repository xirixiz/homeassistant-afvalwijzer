from datetime import datetime, timedelta

from ..common.day_sensor_data import DaySensorData
from ..common.next_sensor_data import NextSensorData
from ..const.const import _LOGGER

# import sys
# def excepthook(type, value, traceback):
#     _LOGGER.error(value)
# sys.excepthook = excepthook


class WasteDataTransformer(object):

    ##########################################################################
    #  INIT
    ##########################################################################
    def __init__(
        self,
        waste_data_raw,
        exclude_pickup_today,
        exclude_list,
        default_label,
    ):
        waste_data_raw.sort(key=lambda item: datetime.strptime(item["date"], "%Y-%m-%d"))
        self.waste_data_raw = waste_data_raw
        self.exclude_pickup_today = exclude_pickup_today
        self.exclude_list = exclude_list.strip().lower()
        self.default_label = default_label

        TODAY = datetime.now().strftime("%d-%m-%Y")
        self.DATE_TODAY = datetime.strptime(TODAY, "%d-%m-%Y")
        self.DATE_TOMORROW = datetime.strptime(TODAY, "%d-%m-%Y") + timedelta(days=1)

        (
            self._waste_data_with_today,
            self._waste_data_without_today,
        ) = self.__structure_waste_data()  # type: ignore

        (
            self._waste_data_provider,
            self._waste_types_provider,
            self._waste_data_custom,
            self._waste_types_custom,
        ) = self.__gen_sensor_waste_data()

    ##########################################################################
    # STRUCTURE ALL WASTE DATA IN CUSTOM FORMAT
    #########################################################################

    def __structure_waste_data(self):
        try:
            waste_data_with_today = {}
            waste_data_without_today = {}

            for item in self.waste_data_raw:
                item_date = datetime.strptime(item["date"], "%Y-%m-%d")
                item_name = item["type"].strip().lower()
                if (
                    item_name not in self.exclude_list
                    and item_name not in waste_data_with_today
                    and item_date >= self.DATE_TODAY
                ):
                    waste_data_with_today[item_name] = item_date

            for item in self.waste_data_raw:
                item_date = datetime.strptime(item["date"], "%Y-%m-%d")
                item_name = item["type"].strip().lower()
                if (
                    item_name not in self.exclude_list
                    and item_name not in waste_data_without_today
                    and item_date > self.DATE_TODAY
                ):
                    waste_data_without_today[item_name] = item_date

            try:
                for item in self.waste_data_raw:
                    item_name = item["type"].strip().lower()
                    if item_name not in self.exclude_list:
                        if item_name not in waste_data_with_today.keys():
                            waste_data_with_today[item_name] = self.default_label
                        if item_name not in waste_data_without_today.keys():
                            waste_data_without_today[item_name] = self.default_label
            except Exception as err:
                _LOGGER.error(f"Other error occurred: {err}")

            return waste_data_with_today, waste_data_without_today
        except Exception as err:
            _LOGGER.error(f"Other error occurred: {err}")

    ##########################################################################
    # GENERATE REQUIRED DATA FOR HASS SENSORS
    ##########################################################################
    def __gen_sensor_waste_data(self):
        if self.exclude_pickup_today.casefold() in ("false", "no"):
            date_selected = self.DATE_TODAY
            waste_data_provider = self._waste_data_with_today
        else:
            date_selected = self.DATE_TOMORROW
            waste_data_provider = self._waste_data_without_today

        try:
            waste_types_provider = sorted(
                {
                    waste["type"]
                    for waste in self.waste_data_raw
                    if waste["type"] not in self.exclude_list
                }
            )

        except Exception as err:
            _LOGGER.error(f"Other error occurred waste_types_provider: {err}")

        try:
            waste_data_formatted = [
                {
                    "type": waste["type"],
                    "date": datetime.strptime(waste["date"], "%Y-%m-%d"),
                }
                for waste in self.waste_data_raw
                if waste["type"] in waste_types_provider
            ]

        except Exception as err:
            _LOGGER.error(f"Other error occurred waste_data_formatted: {err}")

        days = DaySensorData(waste_data_formatted, self.default_label)

        try:
            waste_data_after_date_selected = list(
                filter(
                    lambda waste: waste["date"] >= date_selected, waste_data_formatted
                )
            )
        except Exception as err:
            _LOGGER.error(f"Other error occurred waste_data_after_date_selected: {err}")

        next_data = NextSensorData(waste_data_after_date_selected, self.default_label)

        try:
            waste_data_custom = {**next_data.next_sensor_data, **days.day_sensor_data}
        except Exception as err:
            _LOGGER.error(f"Other error occurred waste_data_custom: {err}")

        try:
            waste_types_custom = list(sorted(waste_data_custom.keys()))
        except Exception as err:
            _LOGGER.error(f"Other error occurred waste_types_custom: {err}")

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
