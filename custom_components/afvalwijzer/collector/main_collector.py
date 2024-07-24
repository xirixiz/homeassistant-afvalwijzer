from ..common.waste_data_transformer import WasteDataTransformer
from ..const.const import (
    _LOGGER,
    SENSOR_COLLECTORS_AFVALWIJZER,
    SENSOR_COLLECTORS_BURGERPORTAAL,
    SENSOR_COLLECTORS_CIRCULUS,
    SENSOR_COLLECTORS_DEAFVALAPP,
    SENSOR_COLLECTORS_ICALENDAR,
    SENSOR_COLLECTORS_OPZET,
    SENSOR_COLLECTORS_RD4,
    SENSOR_COLLECTORS_XIMMIO
)

try:
    from . import burgerportaal, circulus, deafvalapp, icalendar, mijnafvalwijzer, opzet, rd4, rwm, ximmio
except ImportError as err:
    _LOGGER.error(f"Import error {err.args}")


class MainCollector(object):
    def __init__(
        self,
        provider,
        postal_code,
        street_number,
        suffix,
        exclude_pickup_today,
        date_isoformat,
        exclude_list,
        default_label,
    ):
        self.provider = provider.strip().lower()
        self.postal_code = postal_code.strip().upper()
        self.street_number = street_number.strip()
        self.suffix = suffix.strip().lower()
        self.exclude_pickup_today = exclude_pickup_today.strip()
        self.date_isoformat = date_isoformat.strip()
        self.exclude_list = exclude_list.strip().lower()
        self.default_label = default_label.strip()

        try:
            if provider in SENSOR_COLLECTORS_AFVALWIJZER:
                waste_data_raw = mijnafvalwijzer.get_waste_data_raw(
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
            elif provider in SENSOR_COLLECTORS_XIMMIO.keys():
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
                return False

        except ValueError as err:
            _LOGGER.error(f"Check afvalwijzer platform settings {err.args}")

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
