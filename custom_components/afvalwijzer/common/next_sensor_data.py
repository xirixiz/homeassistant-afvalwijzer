from datetime import datetime

from ..const.const import _LOGGER


class NextSensorData(object):
    def __init__(self, waste_data_after_date_selected, default_label):
        self.waste_data_after_date_selected = sorted(
            waste_data_after_date_selected, key=lambda d: d["date"]
        )

        TODAY = datetime.now().strftime("%d-%m-%Y")
        self.today_date = datetime.strptime(TODAY, "%d-%m-%Y")
        self.default_label = default_label

        self.next_waste_date, self.next_waste_in_days, self.next_waste_type = self._calculate_next_waste()

        self.data = self._gen_next_sensor_data()

    def _calculate_next_waste(self):
        next_waste_date = self.default_label
        next_waste_in_days = self.default_label
        next_waste_type = []

        try:
            next_waste_date = self.waste_data_after_date_selected[0]["date"]
            next_waste_in_days = abs(self.today_date - next_waste_date).days

            for waste in self.waste_data_after_date_selected:
                item_date = waste["date"]
                if item_date == next_waste_date:
                    item_name = waste["type"]
                    next_waste_type.append(item_name)

            if not next_waste_type:
                next_waste_type.append(self.default_label)
        except Exception as err:
            _LOGGER.error(f"Error occurred while calculating next waste: {err}")

        return next_waste_date, next_waste_in_days, next_waste_type

    def _gen_next_sensor_data(self):
        next_sensor = {}
        try:
            next_sensor["next_date"] = self.next_waste_date
            next_sensor["next_in_days"] = self.next_waste_in_days
            next_sensor["next_type"] = ", ".join(self.next_waste_type)
        except Exception as err:
            _LOGGER.error(f"Error occurred while generating next sensor data: {err}")

        return next_sensor

    @property
    def next_sensor_data(self):
        return self.data
