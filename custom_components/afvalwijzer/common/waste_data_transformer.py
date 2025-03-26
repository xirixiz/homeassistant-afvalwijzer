from datetime import datetime, timedelta

from ..common.day_sensor_data import DaySensorData
from ..common.next_sensor_data import NextSensorData
from ..const.const import _LOGGER


class WasteDataTransformer:
    def __init__(self, waste_data_raw, exclude_pickup_today, exclude_list, default_label):
        self.default_label = default_label
        # Process exclude_list: assume comma-separated values, creating a set for fast lookup
        self.exclude_list = {item.strip().lower() for item in exclude_list.split(",")} if exclude_list else set()

        _LOGGER.info("Initializing WasteDataTransformer with %d raw waste items", len(waste_data_raw))

        # Convert each raw waste data item's date once and normalize type strings.
        for item in waste_data_raw:
            item["date_obj"] = datetime.strptime(item["date"], "%Y-%m-%d").date()
            item["type"] = item["type"].strip().lower()

        # Sort waste data by the new date_obj field.
        self.waste_data_raw = sorted(waste_data_raw, key=lambda item: item["date_obj"])
        _LOGGER.info("Sorted waste data by date.")

        today = datetime.now().date()
        self.date_today = today
        self.date_tomorrow = today + timedelta(days=1)
        _LOGGER.info("Today's date: %s, Tomorrow's date: %s", self.date_today, self.date_tomorrow)

        self._waste_data_with_today, self._waste_data_without_today = self._structure_waste_data()
        _LOGGER.info(
            "Structured waste data: %d types with today, %d types without today",
            len(self._waste_data_with_today),
            len(self._waste_data_without_today)
        )

        (
            self._waste_data_provider,
            self._waste_types_provider,
            self._waste_data_custom,
            self._waste_types_custom,
        ) = self._generate_sensor_waste_data(exclude_pickup_today)
        _LOGGER.info(
            "Generated sensor waste data with %d provider types and %d custom types",
            len(self._waste_types_provider),
            len(self._waste_types_custom)
        )

    def _structure_waste_data(self):
        waste_data_with_today = {}
        waste_data_without_today = {}
        all_types = set()

        # Iterate once over the raw data to build the dictionaries.
        for item in self.waste_data_raw:
            item_date = item["date_obj"]
            item_type = item["type"]

            if item_type in self.exclude_list:
                continue

            all_types.add(item_type)
            if item_date >= self.date_today and item_type not in waste_data_with_today:
                waste_data_with_today[item_type] = item_date
            if item_date > self.date_today and item_type not in waste_data_without_today:
                waste_data_without_today[item_type] = item_date

        # Ensure every type is present by adding missing keys with the default label.
        for item_type in all_types:
            if item_type not in waste_data_with_today:
                waste_data_with_today[item_type] = self.default_label
            if item_type not in waste_data_without_today:
                waste_data_without_today[item_type] = self.default_label

        _LOGGER.info("Completed structuring waste data for types: %s", sorted(all_types))
        return waste_data_with_today, waste_data_without_today

    def _generate_sensor_waste_data(self, exclude_pickup_today):
        # Choose date and provider based on exclude_pickup_today flag.
        if exclude_pickup_today.strip().lower() in ("false", "no"):
            date_selected = self.date_today
            waste_data_provider = self._waste_data_with_today
        else:
            date_selected = self.date_tomorrow
            waste_data_provider = self._waste_data_without_today

        _LOGGER.info(
            "Selected date for sensor data: %s based on exclude_pickup_today flag '%s'",
            date_selected, exclude_pickup_today
        )

        # Build a sorted list of waste types not in the exclusion list.
        waste_types_provider = sorted(
            {item["type"] for item in self.waste_data_raw if item["type"] not in self.exclude_list}
        )
        _LOGGER.info("Provider waste types: %s", waste_types_provider)

        # Create a formatted list of waste data with the date converted.
        waste_data_formatted = [
            {"type": item["type"], "date": item["date_obj"]}
            for item in self.waste_data_raw
            if item["type"] not in self.exclude_list
        ]
        _LOGGER.info("Formatted waste data count: %d", len(waste_data_formatted))

        # Generate sensor data from external classes.
        days = DaySensorData(waste_data_formatted, self.default_label)
        _LOGGER.info("DaySensorData generated with %d entries", len(days.day_sensor_data))
        waste_data_after_date_selected = [
            item for item in waste_data_formatted if item["date"] >= date_selected
        ]
        _LOGGER.info("Filtered waste data after selected date (%s) count: %d", date_selected, len(waste_data_after_date_selected))
        next_data = NextSensorData(waste_data_after_date_selected, self.default_label)
        _LOGGER.info("NextSensorData generated with %d entries", len(next_data.next_sensor_data))

        # Merge dictionaries (with next_data taking precedence on key collisions).
        waste_data_custom = {**days.day_sensor_data, **next_data.next_sensor_data}
        waste_types_custom = sorted(waste_data_custom.keys())
        _LOGGER.info("Custom sensor data generated with types: %s", waste_types_custom)

        return waste_data_provider, waste_types_provider, waste_data_custom, waste_types_custom

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
