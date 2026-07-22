"""Transform raw waste data into structures used by Afvalwijzer sensors."""

from datetime import datetime, timedelta

from homeassistant.util import dt as dt_util

from ..common.day_sensor_data import DaySensorData
from ..common.next_sensor_data import NextSensorData


class WasteDataTransformer:
    """Transform raw waste data into structures used by sensors."""

    def __init__(
        self,
        waste_data_raw,
        exclude_pickup_today,
        exclude_list,
        default_label,
    ):
        """Initialize the waste data transformer.

        Prepare raw waste data and generate derived datasets for sensor use.
        """
        parsed_data = [
            {
                "type": item["type"],
                "date": datetime.strptime(item["date"], "%Y-%m-%d"),
            }
            for item in waste_data_raw
            if item["type"].strip().lower() != "ignore"
        ]
        parsed_data.sort(key=lambda item: item["date"])
        self.waste_data_raw = parsed_data
        self.exclude_pickup_today = exclude_pickup_today
        self.exclude_set = {
            x.strip() for x in exclude_list.strip().lower().split(",") if x.strip()
        }
        self.default_label = default_label

        now = dt_util.now()
        today_date = now.date()
        self.DATE_TODAY = datetime(today_date.year, today_date.month, today_date.day)
        self.DATE_TOMORROW = self.DATE_TODAY + timedelta(days=1)

        (
            self._waste_data_with_today,
            self._waste_data_without_today,
        ) = self._structure_waste_data()  # type: ignore

        (
            self._waste_data_provider,
            self._waste_types_provider,
            self._waste_data_custom,
            self._waste_types_custom,
        ) = self._gen_sensor_waste_data()

    def _structure_waste_data(self):
        waste_data_with_today = {}
        waste_data_without_today = {}

        if self.exclude_pickup_today.casefold() in ("false", "no"):
            cutoff_date = self.DATE_TODAY
        else:
            cutoff_date = self.DATE_TOMORROW

        for item in self.waste_data_raw:
            item_date = item["date"]
            item_name = item["type"].strip().lower()

            if (
                item_name not in self.exclude_set
                and item_name not in waste_data_with_today
                and item_date >= self.DATE_TODAY
            ):
                waste_data_with_today[item_name] = item_date

            if (
                item_name not in self.exclude_set
                and item_name not in waste_data_without_today
                and item_date >= cutoff_date
            ):
                waste_data_without_today[item_name] = item_date

        for item in self.waste_data_raw:
            item_name = item["type"].strip().lower()
            if item_name not in self.exclude_set:
                waste_data_with_today.setdefault(item_name, self.default_label)
                waste_data_without_today.setdefault(item_name, self.default_label)

        return waste_data_with_today, waste_data_without_today

    def _gen_sensor_waste_data(self):
        if self.exclude_pickup_today.casefold() in ("false", "no"):
            date_selected = self.DATE_TODAY
            waste_data_provider = self._waste_data_with_today
        else:
            date_selected = self.DATE_TOMORROW
            waste_data_provider = self._waste_data_without_today

        waste_types_provider = sorted(
            {
                waste["type"]
                for waste in self.waste_data_raw
                if waste["type"] not in self.exclude_set
            }
        )

        waste_data_formatted = [
            {
                "type": waste["type"],
                "date": waste["date"],
            }
            for waste in self.waste_data_raw
            if waste["type"] in waste_types_provider
        ]

        days = DaySensorData(waste_data_formatted, self.default_label)

        waste_data_after_date_selected = [
            waste for waste in waste_data_formatted if waste["date"] >= date_selected
        ]

        next_data = NextSensorData(waste_data_after_date_selected, self.default_label)

        waste_data_custom = {
            **next_data.next_sensor_data,
            **days.day_sensor_data,
        }

        waste_types_custom = sorted(waste_data_custom.keys())

        return (
            waste_data_provider,
            waste_types_provider,
            waste_data_custom,
            waste_types_custom,
        )

    @property
    def waste_data_with_today(self):
        """Return waste data including today."""
        return self._waste_data_with_today

    @property
    def waste_data_without_today(self):
        """Return waste data excluding today."""
        return self._waste_data_without_today

    @property
    def waste_data_provider(self):
        """Return provider specific waste data."""
        return self._waste_data_provider

    @property
    def waste_types_provider(self):
        """Return provider specific waste types."""
        return self._waste_types_provider

    @property
    def waste_data_custom(self):
        """Return combined custom waste data."""
        return self._waste_data_custom

    @property
    def waste_types_custom(self):
        """Return custom waste data keys."""
        return self._waste_types_custom
