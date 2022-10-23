#!/usr/bin/env python3
"""
Sensor component for AfvalDienst
Author: Bram van Dartel - xirixiz

import afvalwijzer
from afvalwijzer.collector.mijnafvalwijzer import AfvalWijzer
AfvalWijzer().get_data('','','')

python3 -m afvalwijzer.test.test_module

"""

from ..collector.deafvalapp import DeAfvalappCollector
from ..collector.icalendar import IcalendarCollector
from ..collector.mijnafvalwijzer import MijnAfvalWijzerCollector
from ..collector.opzet import OpzetCollector
from ..collector.rd4 import Rd4Collector
from ..collector.ximmio import XimmioCollector
from ..const.const import (
    SENSOR_COLLECTORS_AFVALWIJZER,
    SENSOR_COLLECTORS_DEAFVALAPP,
    SENSOR_COLLECTORS_ICALENDAR,
    SENSOR_COLLECTORS_OPZET,
    SENSOR_COLLECTORS_RD4,
    SENSOR_COLLECTORS_XIMMIO,
)

# provider = "afvalstoffendienstkalender"
# api_token = "5ef443e778f41c4f75c69459eea6e6ae0c2d92de729aa0fc61653815fbd6a8ca"

# Afvalstoffendienstkalender
# postal_code = "5391KE"
# street_number = "1"

# Common
suffix = ""
exclude_pickup_today = "True"
default_label = "Geen"
exclude_list = ""

# Afvalwijzer
# provider = "mijnafvalwijzer"
# postal_code = "5146EG"
# street_number = "6"

# Afvalwijzer
# provider = "mijnafvalwijzer"
# postal_code = "9726BA"
# street_number = "11"

# DeAfvalapp
provider = "deafvalapp"
postal_code = "6105CN"
street_number = "1"

# Ximmio
# provider = "meerlanden"
# postal_code = "2201XZ"
# street_number = "38"

# Ximmio
# provider = "meerlanden"
# postal_code = "2121xt"
# street_number = "38"

# Ximmio
# provider = "acv"
# postal_code = "6713CG"
# street_number = "11"

# Twente
# provider = "twentemilieu"
# postal_code = "7642JH"
# street_number = "5"

# provider = "prezero"
# postal_code = "6665CN"
# street_number = "1"

# RD4
# provider = "rd4"
# postal_code = "6301ET"
# street_number = "24"
# suffix = "C"

# Icalendar
# provider = "eemsdelta"
# postal_code = "9991AB"
# street_number = "2"


postal_code = postal_code.strip().upper()

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
elif provider == SENSOR_COLLECTORS_DEAFVALAPP:
    collector = DeAfvalappCollector(
        provider,
        postal_code,
        street_number,
        suffix,
        exclude_pickup_today,
        exclude_list,
        default_label,
    )
elif provider == SENSOR_COLLECTORS_RD4:
    collector = Rd4Collector(
        provider,
        postal_code,
        street_number,
        suffix,
        exclude_pickup_today,
        exclude_list,
        default_label,
    )

# data = XimmioCollector().get_waste_data_provider("meerlanden", postal_code2, street_number2, suffix, default_label, exclude_list)
# data2 = MijnAfvalWijzerCollector().get_waste_data_provider("mijnafvalwijzer", postal_code, street_number, suffix, default_label, exclude_list)


#########################################################################################################
print("\n")

print(collector.waste_data_with_today)
print(collector.waste_data_without_today)
print(collector.waste_data_custom)
print(collector.waste_types_provider)
print(collector.waste_types_custom)

print("\n")

# for key, value in afval1.items():
#     print(key, value)

# print("\n")

# for key, value in afval2.items():
#     print(key, value)
