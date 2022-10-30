from ..common.waste_data_transformer import WasteDataTransformer
from ..const.const import (
    _LOGGER,
    SENSOR_COLLECTOR_TO_URL,
    SENSOR_COLLECTORS_AFVALWIJZER,
    SENSOR_COLLECTORS_DEAFVALAPP,
    SENSOR_COLLECTORS_ICALENDAR,
    SENSOR_COLLECTORS_OPZET,
    SENSOR_COLLECTORS_RD4,
    SENSOR_COLLECTORS_XIMMIO,
)
from .deafvalapp import DeAfvalappCollector
from .icalendar import IcalendarCollector
from .mijnafvalwijzer import MijnAfvalWijzerCollector
from .opzet import OpzetCollector
from .rd4 import Rd4Collector
from .ximmio import XimmioCollector


class MainCollector(object):
    def __init__(
        self,
        provider,
        postal_code,
        street_number,
        suffix,
        exclude_pickup_today,
        exclude_list,
        default_label,
    ):
        self.provider = provider
        self.postal_code = postal_code = postal_code.strip().upper()
        self.street_number = street_number
        self.suffix = suffix
        self.exclude_pickup_today = exclude_pickup_today
        self.exclude_list = exclude_list.strip().lower()
        self.default_label = default_label

        try:
            if provider in SENSOR_COLLECTORS_AFVALWIJZER:
                collector = MijnAfvalWijzerCollector(
                    provider,
                    postal_code,
                    street_number,
                    suffix,
                    exclude_pickup_today,
                    exclude_list,
                    default_label,
                )
            elif provider in SENSOR_COLLECTORS_OPZET.keys():
                collector = OpzetCollector(
                    provider,
                    postal_code,
                    street_number,
                    suffix,
                    exclude_pickup_today,
                    exclude_list,
                    default_label,
                )
            elif provider in SENSOR_COLLECTORS_XIMMIO.keys():
                collector = XimmioCollector(
                    provider,
                    postal_code,
                    street_number,
                    suffix,
                    exclude_pickup_today,
                    exclude_list,
                    default_label,
                )
            elif provider in SENSOR_COLLECTORS_ICALENDAR.keys():
                collector = IcalendarCollector(
                    provider,
                    postal_code,
                    street_number,
                    suffix,
                    exclude_pickup_today,
                    exclude_list,
                    default_label,
                )
            elif provider in SENSOR_COLLECTORS_DEAFVALAPP.keys():
                collector = DeAfvalappCollector(
                    provider,
                    postal_code,
                    street_number,
                    suffix,
                    exclude_pickup_today,
                    exclude_list,
                    default_label,
                )
            elif provider in SENSOR_COLLECTORS_RD4.keys():
                collector = Rd4Collector(
                    provider,
                    postal_code,
                    street_number,
                    suffix,
                    exclude_pickup_today,
                    exclude_list,
                    default_label,
                )
            else:
                _LOGGER.error(f"Unknown provider: {provider}")
                return False

        except ValueError as err:
            _LOGGER.error(f"Check afvalwijzer platform settings {err.args}")

        waste_data_raw = collector.waste_data_raw

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
