from ..common.waste_data_transformer import WasteDataTransformer
from ..const.const import (
    _LOGGER,
    SENSOR_COLLECTORS_CLEANPROFS
)

try:
    from . import cleanprofs
except ImportError as err:
    _LOGGER.error(f"Secondary Collector import error {err.args}")

class SecondaryCollector(object):
    def __init__(
            self,
            secondary_provider,
            postal_code,
            street_number,
            suffix,
            exclude_pickup_today,
            date_isoformat,
            exclude_list,
            default_label
    ):

        # Ensure provider and address field are strings
        self.secondary_provider = str(secondary_provider).strip().lower()
        self.postal_code = str(postal_code).strip().lower()
        self.street_number = str(street_number).strip()
        self.suffix = str(suffix).strip().lower()

        # Handle boolean and string parameters correctly
        self.exclude_pickup_today = str(exclude_pickup_today).lower() if isinstance(
            exclude_pickup_today, bool) else str(exclude_pickup_today).strip().lower()
        self.date_isoformat = str(date_isoformat).lower() if isinstance(
            date_isoformat, bool) else str(date_isoformat).strip().lower()
        self.exclude_list = str(exclude_list).strip().lower()
        self.default_label = str(default_label).strip()

        # Validate and process the provider
        try:
            if secondary_provider in SENSOR_COLLECTORS_CLEANPROFS.keys():
                waste_data_raw = cleanprofs.get_waste_data_raw(
                    self.secondary_provider,
                    self.postal_code,
                    self.street_number,
                    self.suffix,
                )
            else:
                _LOGGER.error(f"Secondary Collector  unkown provider: {secondary_provider}")
                raise ValueError(f"Secondary Collector unknown provider: {secondary_provider}")
            
        except ValueError as err:
            _LOGGER.error(f"Secondary Collector platform settings: {err}")
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