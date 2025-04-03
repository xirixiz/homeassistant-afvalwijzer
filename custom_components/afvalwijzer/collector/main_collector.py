from ..common.waste_data_transformer import WasteDataTransformer
from ..const.const import (
    _LOGGER,
    SENSOR_COLLECTORS_AFVALWIJZER,
    SENSOR_COLLECTORS_AFVALALERT,
    SENSOR_COLLECTORS_BURGERPORTAAL,
    SENSOR_COLLECTORS_CIRCULUS,
    SENSOR_COLLECTORS_DEAFVALAPP,
    SENSOR_COLLECTORS_ICALENDAR,
    SENSOR_COLLECTORS_KLIKOGROEP,
    SENSOR_COLLECTORS_OPZET,
    SENSOR_COLLECTORS_RD4,
    SENSOR_COLLECTORS_ROVA,
    SENSOR_COLLECTORS_XIMMIO_IDS,
    SENSOR_COLLECTORS_IRADO,
)

try:
    from . import afvalalert, burgerportaal, circulus, deafvalapp, icalendar, irado, klikogroep, mijnafvalwijzer, opzet, rd4, rova, rwm, ximmio
except ImportError as err:
    _LOGGER.error(f"Import error {err.args}")


def normalize_bool_param(param) -> str:
    """
    Normalizes a parameter that might be a boolean or string into a lowercase string.
    """
    if isinstance(param, bool):
        return str(param).lower()
    return str(param).strip().lower()

class MainCollector:
    """
    MainCollector collects and transforms waste data from various providers.
    """

    def __init__(
        self,
        provider: str,
        postal_code: str,
        street_number: str,
        suffix: str,
        username: str,
        password: str,
        exclude_pickup_today,
        date_isoformat,
        exclude_list: str,
        default_label: str,
    ):
        # Normalize input parameters
        self.provider = str(provider).strip().lower()
        self.postal_code = str(postal_code).strip().upper()
        self.street_number = str(street_number).strip()
        self.suffix = str(suffix).strip().lower()
        self.username = str(username).strip().lower()
        self.password = str(password)

        self.exclude_pickup_today = normalize_bool_param(exclude_pickup_today)
        self.date_isoformat = normalize_bool_param(date_isoformat)
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

    def _get_waste_data_raw(self):
        """
        Determines the correct provider module to call based on the provider and retrieves raw waste data.
        """
        try:
            # List of providers with common parameter signatures
            common_providers = [
                (SENSOR_COLLECTORS_AFVALWIJZER, mijnafvalwijzer.get_waste_data_raw),
                (SENSOR_COLLECTORS_AFVALALERT, afvalalert.get_waste_data_raw),
                (SENSOR_COLLECTORS_BURGERPORTAAL, burgerportaal.get_waste_data_raw),
                (SENSOR_COLLECTORS_CIRCULUS, circulus.get_waste_data_raw),
                (SENSOR_COLLECTORS_DEAFVALAPP, deafvalapp.get_waste_data_raw),
                (SENSOR_COLLECTORS_ICALENDAR, icalendar.get_waste_data_raw),
                (SENSOR_COLLECTORS_IRADO, irado.get_waste_data_raw),
                (SENSOR_COLLECTORS_OPZET, opzet.get_waste_data_raw),
                (SENSOR_COLLECTORS_RD4, rd4.get_waste_data_raw),
                (SENSOR_COLLECTORS_ROVA, rova.get_waste_data_raw),
                (SENSOR_COLLECTORS_XIMMIO_IDS, ximmio.get_waste_data_raw),
            ]
            for sensor_set, getter in common_providers:
                # sensor_set might be a list or a dict (using its keys)
                keys = sensor_set.keys() if isinstance(sensor_set, dict) else sensor_set
                if self.provider in keys:
                    return getter(self.provider, self.postal_code, self.street_number, self.suffix)

            # Providers with unique parameter requirements
            if self.provider in SENSOR_COLLECTORS_KLIKOGROEP:
                return klikogroep.get_waste_data_raw(self.provider, self.username, self.password)
            if self.provider == "rwm":
                return rwm.get_waste_data_raw(self.provider, self.postal_code, self.street_number, self.suffix)

            _LOGGER.error(f"Unknown provider: {self.provider}")
            raise ValueError(f"Unknown provider: {self.provider}")

        except ValueError as err:
            _LOGGER.error(f"Check afvalwijzer platform settings: {err}")
            raise

    @property
    def waste_data_with_today(self):
        return self._waste_data.waste_data_with_today

    @property
    def waste_data_without_today(self):
        return self._waste_data.waste_data_without_today

    @property
    def waste_data_provider(self):
        return self._waste_data.waste_data_provider

    @property
    def waste_types_provider(self):
        return self._waste_data.waste_types_provider

    @property
    def waste_data_custom(self):
        return self._waste_data.waste_data_custom

    @property
    def waste_types_custom(self):
        return self._waste_data.waste_types_custom
