from datetime import datetime
import re

import requests

from ..common.waste_data_transformer import WasteDataTransformer
from ..const.const import _LOGGER, SENSOR_COLLECTORS_ICALENDAR


class IcalendarCollector(object):
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
        self.postal_code = postal_code
        self.street_number = street_number
        self.suffix = suffix
        self.exclude_pickup_today = exclude_pickup_today
        self.exclude_list = exclude_list.strip().lower()
        self.default_label = default_label

        if self.provider not in SENSOR_COLLECTORS_ICALENDAR.keys():
            raise ValueError("Invalid provider: %s, please verify", self.provider)

        self.DATE_PATTERN = re.compile(r"^\d{8}")

        self._get_waste_data_provider()

    def _get_waste_data_provider(self):
        try:
            url = SENSOR_COLLECTORS_ICALENDAR[self.provider].format(
                self.provider,
                self.postal_code,
                self.street_number,
                self.suffix,
                datetime.today().strftime("%Y-%m-%d"),
            )
            raw_response = requests.get(url)
        except ValueError:
            raise ValueError("Invalid data received from " + url)

        try:
            response = raw_response.text
        except ValueError:
            raise ValueError("Invalid and/or no data received from " + url)

        if not response:
            _LOGGER.error("No waste data found!")
            return

        self.waste_data_raw = []

        date = None
        type = None
        for line in response.splitlines():
            key, value = line.split(":", 2)
            field = key.split(";")[0]
            if field == "BEGIN" and value == "VEVENT":
                date = None
                type = None
            elif field == "SUMMARY":
                type = value.strip().lower()
            elif field == "DTSTART":
                if self.DATE_PATTERN.match(value):
                    date = f"{value[0:4]}-{value[4:6]}-{value[6:8]}"
                else:
                    _LOGGER.debug("Unsupported date format: %s", value)
            elif field == "END" and value == "VEVENT":
                if date and type:
                    self.waste_data_raw.append({"type": type, "date": date})
                else:
                    _LOGGER.debug(
                        "No date or type extracted from event: date=%s, type=%s",
                        date,
                        type,
                    )

        ##########################################################################
        #  COMMON CODE
        ##########################################################################
        waste_data = WasteDataTransformer(
            self.waste_data_raw,
            self.exclude_pickup_today,
            self.exclude_list,
            self.default_label,
        )

        self._waste_data_with_today = waste_data.waste_data_with_today
        self._waste_data_without_today = waste_data.waste_data_without_today
        self._waste_data_custom = waste_data.waste_data_custom
        self._waste_types_provider = waste_data.waste_types_provider
        self._waste_types_custom = waste_data.waste_types_custom

    ##########################################################################
    #  PROPERTIES FOR EXECUTION
    ##########################################################################
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
