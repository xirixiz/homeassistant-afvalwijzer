"""Generate day-based waste sensor data."""

from datetime import date, datetime, timedelta

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

        # Store as proper timezone-aware date objects for Home Assistant calculations
        self.today_date = dt_util.now().date()
        self.tomorrow_date = self.today_date + timedelta(days=1)
        self.day_after_tomorrow_date = self.today_date + timedelta(days=2)

        self.default_label = default_label

        self.waste_data_today = self.__gen_day_sensor(self.today_date)
        self.waste_data_tomorrow = self.__gen_day_sensor(self.tomorrow_date)
        self.waste_data_dot = self.__gen_day_sensor(self.day_after_tomorrow_date)

        self.data = self._gen_day_sensor_data()

    def __gen_day_sensor(self, target_date):
        day = []
        try:
            for waste in self.waste_data_formatted:
                waste_date = waste["date"]

                if isinstance(waste_date, datetime):
                    waste_date_obj = waste_date.date()
                elif isinstance(waste_date, date):
                    waste_date_obj = waste_date
                elif isinstance(waste_date, str):
                    try:
                        waste_date_obj = datetime.strptime(waste_date, "%Y-%m-%d").date()
                    except ValueError:
                        continue
                else:
                    continue

                # Safe comparison between two date objects
                if waste_date_obj == target_date:
                    day.append(waste["type"])

            # Remove duplicates and apply default label if empty
            waste_types = list(dict.fromkeys(day))
            if not waste_types:
                waste_types.append(self.default_label)

            return waste_types
        except Exception as err:
            _LOGGER.error("Error occurred in __gen_day_sensor: %s", err)
            return []

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
