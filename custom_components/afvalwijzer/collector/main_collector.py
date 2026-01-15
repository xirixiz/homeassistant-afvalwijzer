"""Afvalwijzer integration."""

from ..common.waste_data_transformer import WasteDataTransformer
from ..const.const import (
    _LOGGER,
    SENSOR_COLLECTORS_AFVALALERT,
    SENSOR_COLLECTORS_AMSTERDAM,
    SENSOR_COLLECTORS_BURGERPORTAAL,
    SENSOR_COLLECTORS_CIRCULUS,
    SENSOR_COLLECTORS_DEAFVALAPP,
    SENSOR_COLLECTORS_IRADO,
    SENSOR_COLLECTORS_KLIKOGROEP,
    SENSOR_COLLECTORS_MIJNAFVALWIJZER,
    SENSOR_COLLECTORS_MONTFERLAND,
    SENSOR_COLLECTORS_OMRIN,
    SENSOR_COLLECTORS_OPZET,
    SENSOR_COLLECTORS_RD4,
    SENSOR_COLLECTORS_RECYCLEAPP,
    SENSOR_COLLECTORS_REINIS,
    SENSOR_COLLECTORS_ROVA,
    SENSOR_COLLECTORS_RWM,
    SENSOR_COLLECTORS_STRAATBEELD,
    SENSOR_COLLECTORS_XIMMIO_IDS,
)

try:
    from . import (
        afvalalert,
        amsterdam,
        burgerportaal,
        circulus,
        deafvalapp,
        irado,
        klikogroep,
        mijnafvalwijzer,
        montferland,
        omrin,
        opzet,
        rd4,
        recycleapp,
        reinis,
        rova,
        rwm,
        straatbeeld,
        ximmio,
    )
except ImportError as err:
    _LOGGER.error(f"Import error {err.args}")


class MainCollector:
    """MainCollector collects and transforms waste data from various providers."""

    def __init__(
        self,
        provider: str,
        postal_code: str,
        street_number: str,
        suffix: str,
        exclude_pickup_today,
        date_isoformat,
        exclude_list: str,
        default_label: str,
    ):
        """Initialize MainCollector with parameters and fetch waste data."""
        # Normalize input parameters
        self.provider = str(provider).strip().lower()
        self.postal_code = str(postal_code).strip().upper()
        self.street_number = str(street_number).strip()
        self.suffix = str(suffix).strip().lower()
        self.exclude_pickup_today = self._normalize_bool_param(exclude_pickup_today)
        self.date_isoformat = self._normalize_bool_param(date_isoformat)
        self.exclude_list = str(exclude_list).strip().lower()
        self.default_label = str(default_label).strip()

        # Get raw waste data using the appropriate provider method
        waste_data_raw = self._get_waste_data_raw()

        # Transform raw waste data
        self._waste_data = WasteDataTransformer(
            waste_data_raw,
            self.exclude_pickup_today,
            self.exclude_list,
            self.default_label,
        )

        # Get notification data
        self._notification_data = self._get_notification_data_raw()

    def _normalize_bool_param(self, param) -> str:
        """Normalize a parameter that might be a boolean or string into a lowercase string."""
        if isinstance(param, bool):
            return str(param).lower()
        return str(param).strip().lower()

    def _get_waste_data_raw(self):
        """Determine the correct provider module to call based on the provider and retrieves raw waste data."""
        try:
            # list of providers with common parameter signatures
            common_providers = [
                (SENSOR_COLLECTORS_MIJNAFVALWIJZER, mijnafvalwijzer.get_waste_data_raw),
                (SENSOR_COLLECTORS_AFVALALERT, afvalalert.get_waste_data_raw),
                (SENSOR_COLLECTORS_AMSTERDAM, amsterdam.get_waste_data_raw),
                (SENSOR_COLLECTORS_BURGERPORTAAL, burgerportaal.get_waste_data_raw),
                (SENSOR_COLLECTORS_CIRCULUS, circulus.get_waste_data_raw),
                (SENSOR_COLLECTORS_DEAFVALAPP, deafvalapp.get_waste_data_raw),
                (SENSOR_COLLECTORS_KLIKOGROEP, klikogroep.get_waste_data_raw),
                (SENSOR_COLLECTORS_MONTFERLAND, montferland.get_waste_data_raw),
                (SENSOR_COLLECTORS_OMRIN, omrin.get_waste_data_raw),
                (SENSOR_COLLECTORS_IRADO, irado.get_waste_data_raw),
                (SENSOR_COLLECTORS_OPZET, opzet.get_waste_data_raw),
                (SENSOR_COLLECTORS_RD4, rd4.get_waste_data_raw),
                (SENSOR_COLLECTORS_RECYCLEAPP, recycleapp.get_waste_data_raw),
                (SENSOR_COLLECTORS_REINIS, reinis.get_waste_data_raw),
                (SENSOR_COLLECTORS_ROVA, rova.get_waste_data_raw),
                (SENSOR_COLLECTORS_RWM, rwm.get_waste_data_raw),
                (SENSOR_COLLECTORS_STRAATBEELD, straatbeeld.get_waste_data_raw),
                (SENSOR_COLLECTORS_XIMMIO_IDS, ximmio.get_waste_data_raw),
            ]
            for sensor_set, getter in common_providers:
                # sensor_set might be a list or a dict (using its keys)
                keys = sensor_set.keys() if isinstance(sensor_set, dict) else sensor_set
                if self.provider in keys:
                    return getter(
                        self.provider, self.postal_code, self.street_number, self.suffix
                    )
            _LOGGER.error(f"Unknown provider: {self.provider}")
            raise ValueError(f"Unknown provider: {self.provider}")

        except ValueError as err:
            _LOGGER.error(f"Check afvalwijzer platform settings: {err}")
            raise

    def _get_notification_data_raw(self):
        """Retrieve notification data from providers that support it.

        Returns an empty list if provider doesn't support notifications.
        """

        try:
            # list of providers with notification support
            notification_providers = [
                (SENSOR_COLLECTORS_OPZET, opzet.get_notification_data_raw),
                (
                    SENSOR_COLLECTORS_MIJNAFVALWIJZER,
                    mijnafvalwijzer.get_notification_data_raw,
                ),
            ]

            for sensor_set, getter in notification_providers:
                keys = sensor_set.keys() if isinstance(sensor_set, dict) else sensor_set
                if self.provider in keys:
                    result = getter(
                        self.provider, self.postal_code, self.street_number, self.suffix
                    )
                    _LOGGER.debug(
                        f"Retrieved {len(result)} notification(s) from {self.provider}"
                    )
                    return result

            # Provider doesn't support notifications
            _LOGGER.debug(f"Provider {self.provider} does not support notifications")
            return []

        except Exception as err:
            _LOGGER.warning(
                f"Could not fetch notification data for {self.provider}: {err}"
            )
            return []

    @property
    def waste_data_with_today(self):
        """Return waste data including today's pickups."""
        return self._waste_data.waste_data_with_today

    @property
    def waste_data_without_today(self):
        """Return waste data excluding today's pickups."""
        return self._waste_data.waste_data_without_today

    @property
    def waste_data_provider(self):
        """Return the waste data provider name."""
        return self._waste_data.waste_data_provider

    @property
    def waste_types_provider(self):
        """Return the waste types provided by the provider."""
        return self._waste_data.waste_types_provider

    @property
    def waste_data_custom(self):
        """Return the custom waste data."""
        return self._waste_data.waste_data_custom

    @property
    def waste_types_custom(self):
        """Return the custom waste types."""
        return self._waste_data.waste_types_custom

    @property
    def notification_data(self):
        """Returns the provider notification data."""
        return self._notification_data

    @property
    def notification_count(self):
        """Returns the number of provider notifications."""
        return len(self._notification_data)
