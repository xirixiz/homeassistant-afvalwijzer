from datetime import datetime, timedelta
from ..const.const import _LOGGER


class DaySensorData:

    def __init__(self, waste_data_formatted, default_label):
        today = datetime.now().strftime("%d-%m-%Y")

        self.waste_data_formatted = sorted(waste_data_formatted, key=lambda d: d["date"])
        self.today_date = datetime.strptime(today, "%d-%m-%Y")
        self.tomorrow_date = self.today_date + timedelta(days=1)
        self.day_after_tomorrow_date = self.today_date + timedelta(days=2)
        self.default_label = default_label

        self.waste_data_today = self.__gen_day_sensor(self.today_date)
        self.waste_data_tomorrow = self.__gen_day_sensor(self.tomorrow_date)
        self.waste_data_dot = self.__gen_day_sensor(self.day_after_tomorrow_date)

        self.data = self._gen_day_sensor_data()

    def __gen_day_sensor(self, date):
        day = []
        try:
            day.extend(
                waste["type"]
                for waste in self.waste_data_formatted
                if waste["date"] == date
            )
            if not day:
                day.append(self.default_label)
        except Exception as err:
            _LOGGER.error(f"Error occurred in __gen_day_sensor: {err}")
        return day

    def _gen_day_sensor_data(self):
        day_sensor = {}
        try:
            day_sensor["today"] = ", ".join(self.waste_data_today)
            day_sensor["tomorrow"] = ", ".join(self.waste_data_tomorrow)
            day_sensor["day_after_tomorrow"] = ", ".join(self.waste_data_dot)
        except Exception as err:
            _LOGGER.error(f"Error occurred in _gen_day_sensor_data: {err}")
        return day_sensor

    @property
    def day_sensor_data(self):
        return self.data
