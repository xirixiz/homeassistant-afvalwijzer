#!/usr/bin/env python3
"""
Sensor component for AfvalDienst
Author: Bram van Dartel - xirixiz

import afvalwijzer
from afvalwijzer.collector.mijnafvalwijzer import AfvalWijzer
AfvalWijzer().get_data('','','')

- Comment out __init__.py
- Update this file with your information (or the information you would like to test with, examples are in that file)
- Then run python3 -m afvalwijzer.tests.test_module from this path <some dir>/homeassistant-afvalwijzer/custom_components

"""

from ..collector.main_collector import MainCollector

# provider = "afvalstoffendienstkalender"
# api_token = "5ef443e778f41c4f75c69459eea6e6ae0c2d92de729aa0fc61653815fbd6a8ca"

# Afvalstoffendienstkalender
# postal_code = "5391KE"
# street_number = "1"

# Common
suffix = ""
exclude_pickup_today = "True"
date_isoformat = "True"
default_label = "geen"
exclude_list = ""
username = ""
password = ""

# DeAfvalapp
# provider = "deafvalapp"
# postal_code = "5701NG"
# street_number = "4"

# Icalendar
# provider = "eemsdelta"
# postal_code = "9991AB"
# street_number = "2"

# Afvalwijzer
# provider = "mijnafvalwijzer"
# postal_code = "5146eg"
# street_number = "1"

# provider = "mijnafvalwijzer"
# postal_code = "5563CM"
# street_number = "22"

provider = "mijnafvalwijzer"
postal_code = "5685AB"
street_number = "57"


# provider = "mijnafvalwijzer"
# postal_code = "3601AC"
# street_number = "10"

# Afvalalert
# provider = "afvalalert"
# postal_code = "7881NW"
# street_number = "4"

# ACV
# provider = "acv"
# postal_code = "6714KK"
# street_number = "20"

# iCalendar file
# provider = "veldhoven"
# postal_code = "5508SB"
# street_number = "51"

# Afvalwijzer
# provider = "mijnafvalwijzer"
# postal_code = "3951en"
# street_number = "1"

# Afvalstoffendienstkalender
# provider = "afvalstoffendienstkalender"
# postal_code = "4266NB"
# street_number = "1"

# provider = "rmn"
# postal_code = "3701XK"
# street_number = "24"
# suffix = "b"

# Opzet
# provider = "prezero"
# postal_code = "6665CN"
# street_number = "1"

# Opzet
# provider = "saver"
# postal_code = "4708LS"
# street_number = "10"

# provider = "prezero"
# postal_code = "6822NG"
# street_number = "1"

# provider = "mijnafvalwijzer"
# postal_code = "3951eb"
# street_number = "1"

# provider = "mijnafvalwijzer"
# postal_code = "3941RK"
# street_number = "50"
# suffix = "B"

# RD4
# provider = "rd4"
# postal_code = "6301ET"
# street_number = "6"

# provider = "rova"
# postal_code = "7671BL"
# street_number = "2"

# provider = "rmn"
# postal_code = "3402TA"
# street_number = "1"

# Ximmio
# provider = "woerden"
# postal_code = "3446GL"
# street_number = "16"

# Ximmio
# provider = "almere"
# postal_code = "1311HG"
# street_number = "20"

# Ximmio
# provider = "acv"
# postal_code = "6713CG"
# street_number = "11"

# Circulus
# provider = "circulus"
# postal_code = "7421AC"
# street_number = "1"

# postal_code = postal_code.strip().upper()

collector = MainCollector(
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
)

# MainCollector(
#     provider,
#     postal_code,
#     street_number,
#     suffix,
#     exclude_pickup_today,
#     exclude_list,
#     default_label,
# )

# data = XimmioCollector().get_waste_data_provider("meerlanden", postal_code2, street_number2, suffix, default_label, exclude_list)
# data2 = MijnAfvalWijzerCollector().get_waste_data_provider("mijnafvalwijzer", postal_code, street_number, suffix, default_label, exclude_list)


#########################################################################################################
print("\n")

print(f"Data collected from: {provider} with postcal code: {postal_code}")
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
