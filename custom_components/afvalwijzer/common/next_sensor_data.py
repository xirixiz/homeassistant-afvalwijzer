from datetime import datetime

from ..const.const import _LOGGER


class NextSensorData(object):

    ##########################################################################
    #  INIT
    ##########################################################################
    def __init__(self, waste_data_after_date_selected, default_label):
        self.waste_data_after_date_selected = sorted(
            waste_data_after_date_selected, key=lambda d: d["date"]
        )

        TODAY = datetime.now().strftime("%d-%m-%Y")
        self.today_date = datetime.strptime(TODAY, "%d-%m-%Y")
        self.default_label = default_label

        self.next_waste_date = self.__get_next_waste_date()
        self.next_waste_in_days = self.__get_next_waste_in_days()
        self.next_waste_type = self.__get_next_waste_type()

        self.data = self._gen_next_sensor_data()

    ##########################################################################
    #  GENERATE NEXT SENSOR(S)
    ##########################################################################

    # Generate sensor next_waste_date
    def __get_next_waste_date(self):
        next_waste_date = self.default_label
        try:
            next_waste_date = self.waste_data_after_date_selected[0]["date"]
        except Exception as err:
            _LOGGER.error(f"Other error occurred _get_next_waste_date: {err}")
        return next_waste_date

    # Generate sensor next_waste_in_days
    def __get_next_waste_in_days(self):
        next_waste_in_days = self.default_label
        try:
            next_waste_in_days = abs(self.today_date - self.next_waste_date).days  # type: ignore
        except Exception as err:
            _LOGGER.error(f"Other error occurred _get_next_waste_in_days: {err}")
        return next_waste_in_days

    # Generate sensor next_waste_type
    def __get_next_waste_type(self):
        next_waste_type = []
        try:
            for waste in self.waste_data_after_date_selected:
                item_date = waste["date"]
                if item_date == self.next_waste_date:
                    item_name = waste["type"]
                    next_waste_type.append(item_name)
            if not next_waste_type:
                next_waste_type.append(self.default_label)
        except Exception as err:
            _LOGGER.error(f"Other error occurred _get_next_waste_type: {err}")
        return next_waste_type

    # Generate sensor data for custom sensors
    def _gen_next_sensor_data(self):
        next_sensor = {}
        try:
            next_sensor["next_date"] = self.next_waste_date
            next_sensor["next_in_days"] = self.next_waste_in_days
            next_sensor["next_type"] = ", ".join(self.next_waste_type)
        except Exception as err:
            _LOGGER.error(f"Other error occurred _gen_next_sensor_data: {err}")
        return next_sensor

    @property
    def next_sensor_data(self):
        return self.data
