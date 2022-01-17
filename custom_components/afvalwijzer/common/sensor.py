#!/usr/bin/env python3
"""
Sensor component for AfvalDienst
Author: Bram van Dartel - xirixiz

import afvalwijzer
from afvalwijzer.collector.afvalwijzer import AfvalWijzer
AfvalWijzer().get_data('','','')

python3 -m afvalwijzer.testing.test_module

"""
from datetime import datetime
from afvalwijzer.collector.afvalwijzer import AfvalWijzerCollector
from afvalwijzer.collector.ximmio import XimmioCollector

from afvalwijzer.common.day_sensor_data import DaySensorData
from afvalwijzer.common.next_sensor_data import NextSensorData
from afvalwijzer.const.const import (
    DATE_TODAY,
    DATE_TOMORROW,
    SENSOR_COLLECTORS_AFVALWIJZER,
    SENSOR_COLLECTORS_XIMMIO,
    _LOGGER,
)

# Common
suffix = ""
exclude_pickup_today = "True"
default_label = "Geen"
exclude_list = ""

# Afvalwijzer
provider = "mijnafvalwijzer"
postal_code = "5146EG"
street_number = "6"

# Ximmio
# provider = "meerlanden"
# postal_code = "2201XZ"
# street_number = "38"

if provider in SENSOR_COLLECTORS_AFVALWIJZER:
    collector = AfvalWijzerCollector(provider, postal_code, street_number, suffix, default_label, exclude_list)
elif provider in SENSOR_COLLECTORS_XIMMIO.keys():
    collector = XimmioCollector(provider, postal_code, street_number, suffix, default_label, exclude_list)

if collector == "":
    raise ValueError("Invalid provider: %s, please verify", provider)

if exclude_pickup_today.casefold() in ("false", "no"):
    date_selected = DATE_TODAY
    waste_data_provider = collector.waste_data_with_today
else:
    date_selected = DATE_TOMORROW
    waste_data_provider = collector.waste_data_without_today

try:
    waste_types_provider = sorted(set(list(waste["type"] for waste in collector.waste_data_raw)))
except Exception as err:
    _LOGGER.error("Other error occurred waste_types_provider: %s", err)

try:
    waste_data_formatted = list(
        {
            "type": waste["type"],
            "date": datetime.strptime(waste["date"], "%Y-%m-%d"),
        }
        for waste in collector.waste_data_raw
        if (waste["type"] in waste_types_provider) and (waste["type"] not in exclude_list)
    )
except Exception as err:
    _LOGGER.error("Other error occurred waste_data_formatted: %s", err)

try:
    waste_data_after_date_selected = list(filter(lambda waste: waste["date"] >= date_selected, waste_data_formatted))
except Exception as err:
    _LOGGER.error("Other error occurred waste_data_after_date_selected: %s", err)

day_sensors = DaySensorData(waste_data_formatted, default_label)
next_sensors = NextSensorData(waste_data_after_date_selected, default_label)

print(day_sensors.day_sensor_data)
print(next_sensors.next_sensor_data)
