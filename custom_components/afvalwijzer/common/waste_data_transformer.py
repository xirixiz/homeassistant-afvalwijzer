"""Afvalwijzer integration."""

from __future__ import annotations

from datetime import datetime, timedelta

from ..common.day_sensor_data import DaySensorData
from ..common.next_sensor_data import NextSensorData
from ..const.const import _LOGGER


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
        self.waste_data_raw = waste_data_raw
        self.exclude_pickup_today = exclude_pickup_today
        self.exclude_list = exclude_list.strip().lower()
        self.exclude_set = {
            x.strip().lower() for x in self.exclude_list.split(",") if x.strip()
        }
        self.default_label = default_label

        today_dt = datetime.now()
        self.DATE_TODAY = datetime.combine(today_dt.date(), datetime.min.time())
        self.DATE_TOMORROW = self.DATE_TODAY + timedelta(days=1)

        # Sort raw input (guard: if raw data is malformed, keep going with empty output)
        try:
            self.waste_data_raw.sort(
                key=lambda item: datetime.strptime(item["date"], "%Y-%m-%d")
            )
        except Exception as err:
            _LOGGER.error("Invalid waste_data_raw format: %s", err)
            self.waste_data_raw = []

        self._waste_data_with_today, self._waste_data_without_today = (
            self.__structure_waste_data()
        )

        (
            self._waste_data_provider,
            self._waste_types_provider,
            self._waste_data_custom,
            self._waste_types_custom,
        ) = self.__gen_sensor_waste_data()

    def __structure_waste_data(self):
        waste_data_with_today: dict[str, datetime | str] = {}
        waste_data_without_today: dict[str, datetime | str] = {}

        for item in self.waste_data_raw:
            item_name = (item.get("type") or "").strip().lower()
            if not item_name or item_name in self.exclude_set:
                continue

            try:
                item_date = datetime.strptime(item["date"], "%Y-%m-%d")
            except Exception:
                continue

            if item_name not in waste_data_with_today and item_date >= self.DATE_TODAY:
                waste_data_with_today[item_name] = item_date

            if (
                item_name not in waste_data_without_today
                and item_date > self.DATE_TODAY
            ):
                waste_data_without_today[item_name] = item_date

        # Keep existing behavior: ensure every seen type exists with default label ("geen")
        for item in self.waste_data_raw:
            item_name = (item.get("type") or "").strip().lower()
            if not item_name or item_name in self.exclude_set:
                continue
            waste_data_with_today.setdefault(item_name, self.default_label)
            waste_data_without_today.setdefault(item_name, self.default_label)

        return waste_data_with_today, waste_data_without_today

    def __gen_sensor_waste_data(self):
        if str(self.exclude_pickup_today).casefold() in ("false", "no", "0", "off"):
            date_selected = self.DATE_TODAY
            waste_data_provider = self._waste_data_with_today
        else:
            date_selected = self.DATE_TOMORROW
            waste_data_provider = self._waste_data_without_today

        # Normalize provider types (strip/lower) so sensors match keys consistently
        waste_types_provider = sorted(
            {
                (waste.get("type") or "").strip().lower()
                for waste in self.waste_data_raw
                if (waste.get("type") or "").strip().lower()
                and (waste.get("type") or "").strip().lower() not in self.exclude_set
            }
        )

        # Build formatted list used by DaySensorData / NextSensorData
        waste_data_formatted: list[dict[str, object]] = []
        for waste in self.waste_data_raw:
            w_type = (waste.get("type") or "").strip().lower()
            if not w_type or w_type not in waste_types_provider:
                continue

            try:
                w_date = datetime.strptime(waste["date"], "%Y-%m-%d")
            except Exception:
                continue

            waste_data_formatted.append({"type": w_type, "date": w_date})

        days = DaySensorData(waste_data_formatted, self.default_label)

        # Compare on date() to avoid datetime-vs-date weirdness and timezone edge cases.
        date_selected_d = date_selected.date()
        waste_data_after_date_selected = [
            waste
            for waste in waste_data_formatted
            if isinstance(waste.get("date"), datetime)
            and waste["date"].date() >= date_selected_d
        ]

        next_data = NextSensorData(waste_data_after_date_selected, self.default_label)

        try:
            waste_data_custom = {
                **next_data.next_sensor_data,
                **days.day_sensor_data,
            }
        except Exception as err:
            _LOGGER.error("Other error occurred waste_data_custom: %s", err)
            waste_data_custom = {}

        try:
            waste_types_custom = sorted(waste_data_custom.keys())
        except Exception as err:
            _LOGGER.error("Other error occurred waste_types_custom: %s", err)
            waste_types_custom = []

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
