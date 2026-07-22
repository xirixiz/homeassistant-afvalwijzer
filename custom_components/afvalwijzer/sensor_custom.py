"""Afvalwijzer custom sensor."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import logging
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util, slugify

from .common.sensor_utils import (
    address_key,
    as_utc_aware,
    build_device_info,
    date_to_local_midnight,
    icon_for_waste_type,
    make_unique_id,
    translate_value,
)
from .const.const import (
    ATTR_DAYS_UNTIL_COLLECTION_DATE,
    ATTR_LAST_UPDATE,
    CONF_COLLECTOR,
    CONF_DEFAULT_LABEL,
    CONF_SHOW_FULL_TIMESTAMP,
    DEFAULT_SHOW_FULL_TIMESTAMP,
    SENSOR_ICON,
    SENSOR_PREFIX,
)

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class _Config:
    default_label: str
    show_full_timestamp: bool


class CustomSensor(CoordinatorEntity, SensorEntity):
    """Representation of a custom based waste sensor."""

    def __init__(
        self,
        hass: Any,
        waste_type: str,
        coordinator: Any,
        config: dict[str, Any],
    ) -> None:
        """Initialize a custom Afvalwijzer sensor."""
        super().__init__(coordinator)
        self.hass = hass
        self.waste_type = waste_type
        self.coordinator = coordinator
        self._config = config

        self._cfg = _Config(
            default_label=str(config.get(CONF_DEFAULT_LABEL, "geen")),
            show_full_timestamp=bool(
                config.get(CONF_SHOW_FULL_TIMESTAMP, DEFAULT_SHOW_FULL_TIMESTAMP)
            ),
        )

        self._last_update: str | None = None
        self._days_until_collection_date: int | None = None

        self._attr_has_entity_name = True
        self._attr_translation_key = waste_type.lower().replace("-", "_")

        addr = address_key(config)
        self.entity_id = f"sensor.{slugify(SENSOR_PREFIX + addr + '_' + waste_type)}"

        self._attr_unique_id = make_unique_id(config, waste_type)
        self._attr_icon = self._icon_for_waste_type(waste_type)

        self._attr_device_class: SensorDeviceClass | None = None
        self._native_value: datetime | str | None = None
        self._fallback_state = self._cfg.default_label

    @property
    def device_info(self):
        """Group all sensors for the same address under one device."""
        return build_device_info(self._config)

    async def async_added_to_hass(self) -> None:
        """Populate initial state from data the coordinator already has."""
        await super().async_added_to_hass()
        if self.coordinator.data is not None:
            self._handle_coordinator_update()

    @staticmethod
    def _icon_for_waste_type(waste_type: str) -> str:
        match waste_type:
            case "today":
                return "mdi:calendar-today"
            case "tomorrow":
                return "mdi:calendar"
            case "day_after_tomorrow":
                return "mdi:calendar-end"
            case "next_date":
                return "mdi:calendar-multiselect"
            case "next_in_days":
                return "mdi:counter"
            case "next_type":
                return "mdi:label-outline"
            case _:
                _LOGGER.debug("No specific icon for: %s", waste_type)
                return SENSOR_ICON

    @property
    def native_value(self) -> datetime | str | None:
        """Return the native value of the sensor."""
        if self._attr_device_class == SensorDeviceClass.TIMESTAMP:
            return (
                self._native_value if isinstance(self._native_value, datetime) else None
            )
        return self._fallback_state

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Apply the fetched value to the sensor state."""
        attrs: dict[str, Any] = {
            ATTR_LAST_UPDATE: self._last_update,
            "collector": self._config.get(CONF_COLLECTOR),
        }
        if "next_date" in (self.waste_type or "").lower():
            attrs[ATTR_DAYS_UNTIL_COLLECTION_DATE] = self._days_until_collection_date
        return attrs

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug("Updating custom sensor from coordinator: %s", self.entity_id)

        try:
            waste_data_custom = self.coordinator.waste_data_custom or {}

            if self.waste_type not in waste_data_custom:
                raise ValueError(f"No data for custom sensor: {self.waste_type}")

            raw_value = waste_data_custom[self.waste_type]
            if self.waste_type == "next_type":
                self._attr_icon = self._next_type_icon(raw_value)
            translated_val = translate_value(raw_value, self._config, self.coordinator)
            self._apply_value(translated_val)
            self._last_update = dt_util.now().isoformat()
            if self._native_value is not None:
                _LOGGER.debug(
                    "Custom sensor %s updated. Value: %s",
                    self.entity_id,
                    self._native_value,
                )
        except Exception as err:
            _LOGGER.error("Error updating custom sensor %s: %s", self.entity_id, err)
            self._set_error_state()

        self.async_write_ha_state()

    @staticmethod
    def _next_type_icon(value: Any) -> str:
        """Return the icon of the waste type the next_type sensor reports.

        Falls back to the generic label icon when the value is not a single
        known waste type (e.g. "gft, papier" or the default label).
        """
        if isinstance(value, str):
            types = [t.strip().lower() for t in value.split(",") if t.strip()]
            if len(types) == 1:
                icon = icon_for_waste_type(types[0])
                if icon:
                    return icon
        return "mdi:label-outline"

    def _apply_value(self, value: Any) -> None:
        """Apply collector output to sensor state."""
        self._days_until_collection_date = None
        self._attr_device_class = None
        self._native_value = None

        if isinstance(value, str):
            parsed = dt_util.parse_datetime(value)
            if parsed is not None:
                value = parsed
            else:
                parsed_date = dt_util.parse_date(value)
                if parsed_date is not None:
                    value = parsed_date

        if isinstance(value, datetime):
            aware = as_utc_aware(value)
            self._set_timestamp(aware)
            return

        if isinstance(value, date):
            aware = date_to_local_midnight(value)
            self._set_timestamp(aware, date_value=value)
            return

        self._fallback_state = str(value)

    def _set_timestamp(
        self, aware_utc: datetime, *, date_value: date | None = None
    ) -> None:
        """Set the sensor as a timestamp sensor."""
        local_dt = aware_utc.astimezone(dt_util.DEFAULT_TIME_ZONE)
        collection_date = date_value or local_dt.date()

        today = dt_util.now().date()
        self._days_until_collection_date = (collection_date - today).days

        if self._cfg.show_full_timestamp:
            self._attr_device_class = SensorDeviceClass.TIMESTAMP
            self._native_value = local_dt
            return

        self._attr_device_class = None
        self._native_value = None
        self._fallback_state = collection_date.isoformat()

    def _set_error_state(self) -> None:
        """Set a safe fallback state on errors."""
        if self.waste_type == "next_type":
            self._attr_icon = "mdi:label-outline"
        self._fallback_state = self._cfg.default_label
        self._days_until_collection_date = None
        self._attr_device_class = None
        self._native_value = None
        self._last_update = dt_util.now().isoformat()
