"""Afvalwijzer integration."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from ..const.const import _LOGGER


class DaySensorData:
    """Generate day-based waste sensor data."""

    def __init__(self, waste_data_formatted, default_label):
        """Initialize day-based sensor data.

        Prepare waste data for today, tomorrow, and the day after tomorrow.
        """
        self.waste_data_formatted = sorted(waste_data_formatted, key=lambda d: d["date"])
        self.default_label = default_label

        today_dt = datetime.now()
        self.today_date = today_dt.date()
        self.tomorrow_date = (today_dt + timedelta(days=1)).date()
        self.day_after_tomorrow_date = (today_dt + timedelta(days=2)).date()

        self.waste_data_today = self.__gen_day_sensor(self.today_date)
        self.waste_data_tomorrow = self.__gen_day_sensor(self.tomorrow_date)
        self.waste_data_dot = self.__gen_day_sensor(self.day_after_tomorrow_date)

        self.data = self._gen_day_sensor_data()

    def __gen_day_sensor(self, target_date: date) -> list[str]:
        day = [
            waste["type"]
            for waste in self.waste_data_formatted
            if isinstance(waste.get("date"), datetime) and waste["date"].date() == target_date
        ]
        return day or [self.default_label]

    def _gen_day_sensor_data(self) -> dict[str, str]:
        """Generate the combined day sensor data dictionary."""
        try:
            return {
                "today": ", ".join(self.waste_data_today),
                "tomorrow": ", ".join(self.waste_data_tomorrow),
                "day_after_tomorrow": ", ".join(self.waste_data_dot),
            }
        except Exception as err:
            _LOGGER.error("Error occurred in _gen_day_sensor_data: %s", err)
            return {}

    @property
    def day_sensor_data(self):
        """Return the prepared day sensor data."""
        return self.data
