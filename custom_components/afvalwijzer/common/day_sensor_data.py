"""Generate day-based waste sensor data."""

from datetime import datetime, timedelta

from homeassistant.util import dt as dt_util

from ..const.const import _LOGGER


class DaySensorData:
    """Generate day-based waste sensor data."""

    def __init__(self, waste_data_formatted, default_label):
        """Initialize day-based sensor data."""

        # Sort using string conversion to prevent crashes if types are mixed upstream
        self.waste_data_formatted = sorted(
            waste_data_formatted, key=lambda d: str(d["date"])
        )

        # Keep as proper datetime.date objects for HA calculations
        self.today_date = dt_util.now().date()
        self.tomorrow_date = self.today_date + timedelta(days=1)
        self.day_after_tomorrow_date = self.today_date + timedelta(days=2)

        self.default_label = default_label

        self.waste_data_today = self._gen_day_sensor(self.today_date)
        self.waste_data_tomorrow = self._gen_day_sensor(self.tomorrow_date)
        self.waste_data_dot = self._gen_day_sensor(self.day_after_tomorrow_date)

        self.data = self._gen_day_sensor_data()

    def _gen_day_sensor(self, target_date):
        day = []
        try:
            for waste in self.waste_data_formatted:
                waste_date = waste["date"]

                # Scenario 1: It's a datetime or date object (Naive or Timezone-Aware)
                if (
                    hasattr(waste_date, "year")
                    and hasattr(waste_date, "month")
                    and hasattr(waste_date, "day")
                ):
                    if (
                        waste_date.year == target_date.year
                        and waste_date.month == target_date.month
                        and waste_date.day == target_date.day
                    ):
                        day.append(waste["type"])

                # Scenario 2: It's a raw string (e.g., "2026-07-09")
                elif isinstance(waste_date, str):
                    try:
                        parsed_date = datetime.strptime(waste_date, "%Y-%m-%d").date()
                        if parsed_date == target_date:
                            day.append(waste["type"])
                    except ValueError:
                        pass

            # De-duplicate and apply the default label (e.g., "geen") if empty
            waste_types = list(dict.fromkeys(day))
            if not waste_types:
                waste_types.append(self.default_label)
            return waste_types

        except Exception as err:
            _LOGGER.error("Error occurred in _gen_day_sensor: %s", err)
            return [self.default_label]

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
