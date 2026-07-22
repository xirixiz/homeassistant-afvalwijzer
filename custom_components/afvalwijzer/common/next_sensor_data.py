"""Generate next-collection waste sensor data."""

from datetime import datetime
import logging

from homeassistant.util import dt as dt_util

_LOGGER = logging.getLogger(__name__)


class NextSensorData:
    """Generate next-collection sensor data."""

    def __init__(self, waste_data_after_date_selected, default_label):
        """Initialize next waste sensor data.

        Prepare data for the next waste collection date, the number of days
        until that date, and the corresponding waste type.
        """
        today = dt_util.now().strftime("%d-%m-%Y")
        self.today_date = datetime.strptime(today, "%d-%m-%Y")
        self.default_label = default_label

        future_waste_data = [
            waste
            for waste in waste_data_after_date_selected
            if waste["date"].date() > self.today_date.date()
        ]

        self.waste_data_after_date_selected = sorted(
            future_waste_data, key=lambda d: d["date"]
        )

        self.next_waste_date = self._get_next_waste_date()
        self.next_waste_in_days = self._get_next_waste_in_days()
        self.next_waste_type = self._get_next_waste_type()

        self.data = self._gen_next_sensor_data()

    def _get_next_waste_date(self):
        if self.waste_data_after_date_selected == []:
            return self.default_label

        try:
            return self.waste_data_after_date_selected[0]["date"]
        except IndexError:
            _LOGGER.error("No waste data found after the selected date.")
            return self.default_label

    def _get_next_waste_in_days(self):
        if self.next_waste_date == self.default_label:
            return self.default_label

        try:
            return abs(self.next_waste_date.date() - dt_util.now().date()).days
        except Exception as err:
            _LOGGER.error("Error occurred in _get_next_waste_in_days: %s", err)
            return self.default_label

    def _get_next_waste_type(self):
        try:
            waste_types = [
                waste["type"]
                for waste in self.waste_data_after_date_selected
                if waste["date"] == self.next_waste_date
            ]
            return list(dict.fromkeys(waste_types)) or [self.default_label]
        except Exception as err:
            _LOGGER.error("Error occurred in _get_next_waste_type: %s", err)
            return [self.default_label]

    def _gen_next_sensor_data(self):
        """Generate the next sensor data dictionary."""
        try:
            return {
                "next_date": self.next_waste_date,
                "next_in_days": self.next_waste_in_days,
                "next_type": ", ".join(self.next_waste_type),
            }
        except Exception as err:
            _LOGGER.error("Error occurred in _gen_next_sensor_data: %s", err)
            return {}

    @property
    def next_sensor_data(self):
        """Return the prepared next sensor data."""
        return self.data
