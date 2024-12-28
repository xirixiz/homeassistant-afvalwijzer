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
    SENSOR_COLLECTORS_XIMMIO_IDS
)

try:
    from . import afvalalert, burgerportaal, circulus, deafvalapp, icalendar, klikogroep, mijnafvalwijzer, opzet, rd4, rova, rwm, ximmio
except ImportError as err:
    _LOGGER.error(f"Import error {err.args}")


class MainCollector(object):
    def __init__(
        self,
        provider,
        postal_code,
        street_number,
        suffix,
        username,
        password,
        exclude_pickup_today,
        date_isoformat,
        exclude_list,
        default_label,
    ):
        # Ensure provider and address fields are strings
        self.provider = str(provider).strip().lower()
        self.postal_code = str(postal_code).strip().upper()
        self.street_number = str(street_number).strip()
        self.suffix = str(suffix).strip().lower()
        self.username = str(username).strip().lower()
        self.password = str(password)

        # Handle boolean and string parameters correctly
        self.exclude_pickup_today = str(exclude_pickup_today).lower() if isinstance(
            exclude_pickup_today, bool) else str(exclude_pickup_today).strip().lower()
        self.date_isoformat = str(date_isoformat).lower() if isinstance(
            date_isoformat, bool) else str(date_isoformat).strip().lower()
        self.exclude_list = str(exclude_list).strip().lower()
        self.default_label = str(default_label).strip()

        # Validate and process the provider
        try:
            if provider in SENSOR_COLLECTORS_AFVALWIJZER:
                waste_data_raw = mijnafvalwijzer.get_waste_data_raw(
                    self.provider,
                    self.postal_code,
                    self.street_number,
                    self.suffix,
                )
            elif provider in SENSOR_COLLECTORS_AFVALALERT.keys():
                waste_data_raw = afvalalert.get_waste_data_raw(
                    self.provider,
                    self.postal_code,
                    self.street_number,
                    self.suffix,
                )
            elif provider in SENSOR_COLLECTORS_BURGERPORTAAL.keys():
                waste_data_raw = burgerportaal.get_waste_data_raw(
                    self.provider,
                    self.postal_code,
                    self.street_number,
                    self.suffix,
                )
            elif provider in SENSOR_COLLECTORS_CIRCULUS.keys():
                waste_data_raw = circulus.get_waste_data_raw(
                    self.provider,
                    self.postal_code,
                    self.street_number,
                    self.suffix,
                )
            elif provider in SENSOR_COLLECTORS_DEAFVALAPP.keys():
                waste_data_raw = deafvalapp.get_waste_data_raw(
                    self.provider,
                    self.postal_code,
                    self.street_number,
                    self.suffix,
                )
            elif provider in SENSOR_COLLECTORS_ICALENDAR.keys():
                waste_data_raw = icalendar.get_waste_data_raw(
                    self.provider,
                    self.postal_code,
                    self.street_number,
                    self.suffix,
                )
            elif provider in SENSOR_COLLECTORS_KLIKOGROEP.keys():
                waste_data_raw = klikogroep.get_waste_data_raw(
                    self.provider,
                    self.username,
                    self.password,
                )
            elif provider in SENSOR_COLLECTORS_OPZET.keys():
                waste_data_raw = opzet.get_waste_data_raw(
                    self.provider,
                    self.postal_code,
                    self.street_number,
                    self.suffix,
                )
            elif provider in SENSOR_COLLECTORS_RD4.keys():
                waste_data_raw = rd4.get_waste_data_raw(
                    self.provider,
                    self.postal_code,
                    self.street_number,
                    self.suffix,
                )
            elif provider in SENSOR_COLLECTORS_ROVA.keys():
                waste_data_raw = rova.get_waste_data_raw(
                    self.provider,
                    self.postal_code,
                    self.street_number,
                    self.suffix,
                )
            elif provider in SENSOR_COLLECTORS_XIMMIO_IDS.keys():
                waste_data_raw = ximmio.get_waste_data_raw(
                    self.provider,
                    self.postal_code,
                    self.street_number,
                    self.suffix,
                )
            elif provider == "rwm":
                waste_data_raw = rwm.get_waste_data_raw(
                    self.provider,
                    self.postal_code,
                    self.street_number,
                    self.suffix,
                )
            else:
                _LOGGER.error(f"Unknown provider: {provider}")
                raise ValueError(f"Unknown provider: {provider}")

        except ValueError as err:
            _LOGGER.error(f"Check afvalwijzer platform settings: {err}")
            raise

        ##########################################################################
        #  COMMON CODE
        ##########################################################################
        self._waste_data = WasteDataTransformer(
            waste_data_raw,
            self.exclude_pickup_today,
            self.exclude_list,
            self.default_label,
        )

    ##########################################################################
    #  PROPERTIES FOR EXECUTION
    ##########################################################################
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
