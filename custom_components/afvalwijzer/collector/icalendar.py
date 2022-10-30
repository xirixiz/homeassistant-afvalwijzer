from datetime import datetime
import re

import requests

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
            raise ValueError(f"Invalid provider: {self.provider}, please verify")

        self.DATE_PATTERN = re.compile(r"^\d{8}")

        self._get_waste_data_provider()

    def _get_waste_data_provider(self):  # sourcery skip: avoid-builtin-shadow
        try:
            url = SENSOR_COLLECTORS_ICALENDAR[self.provider].format(
                self.provider,
                self.postal_code,
                self.street_number,
                self.suffix,
                datetime.now().strftime("%Y-%m-%d"),
            )

            raw_response = requests.get(url)
        except requests.exceptions.RequestException as err:
            raise ValueError(err) from err

        try:
            response = raw_response.text
        except ValueError as exc:
            raise ValueError(f"Invalid and/or no data received from {url}") from exc

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
                    date = f"{value[:4]}-{value[4:6]}-{value[6:8]}"
                else:
                    _LOGGER.debug(f"Unsupported date format: {value}")
            elif field == "END" and value == "VEVENT":
                if date and type:
                    self.waste_data_raw.append({"type": type, "date": date})
                else:
                    _LOGGER.debug(
                        f"No date or type extracted from event: date={date}, type={type}"
                    )
