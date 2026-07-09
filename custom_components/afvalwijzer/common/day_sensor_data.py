"""Generate day-based waste sensor data."""

from datetime import datetime, timedelta

from homeassistant.util import dt as dt_util

from ..const.const import _LOGGER


class DaySensorData:
    """Generate day-based waste sensor data."""

    def __init__(self, waste_data_formatted, default_label):
        """Initialize day-based sensor data.

        Prepare waste data for today, tomorrow, and the day after tomorrow.
        """
        self.waste_data_formatted = sorted(
            waste_data_formatted, key=lambda d: d["date"]
        )

        # 1. Get HA timezone-aware date
        base_date = dt_util.now().date()

        # 2. Convert to midnight datetime objects to perfectly match the transformer data
        self.today_date = datetime.combine(base_date, datetime.min.time())
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
            waste_types = [
                waste["type"]
                for waste in self.waste_data_formatted
                if waste["date"] == date
            ]
            day.extend(list(dict.fromkeys(waste_types)))
            if not day:
                day.append(self.default_label)
        except Exception as err:
            _LOGGER.error("Error occurred in __gen_day_sensor: %s", err)
        return day

    def _gen_day_sensor_data(self):
        """Generate the combined day sensor data dictionary."""
        day_sensor = {}
        try:
            day_sensor["today"] = ", ".join(self.waste_data_today)
            day_sensor["tomorrow"] = ", ".join(self.waste_data_tomorrow)
            day_sensor["day_after_tomorrow"] = ", ".join(self.waste_data_dot)
        except Exception as err:
            _LOGGER.error("Error occurred in _gen_day_sensor_data: %s", err)
        return day_sensor

    @property
    def day_sensor_data(self):
        """Return the prepared day sensor data."""
        return self.data
