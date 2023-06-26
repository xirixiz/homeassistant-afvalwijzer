#!/usr/bin/env python3
"""
Sensor component for AfvalDienst
Author: Bram van Dartel - xirixiz

import afvalwijzer
from afvalwijzer.collector.mijnafvalwijzer import AfvalWijzer
AfvalWijzer().get_data('','','')

python3 -m afvalwijzer.tests.test_module

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
default_label = "geen"
exclude_list = ""

# DeAfvalapp
# provider = "deafvalapp"
# postal_code = "6105CN"
# street_number = "1"

# Icalendar
# provider = "eemsdelta"
# postal_code = "9991AB"
# street_number = "2"

# Afvalwijzer
# provider = "mijnafvalwijzer"
# postal_code = "5146eg"
# street_number = "1"

# Afvalwijzer
provider = "mijnafvalwijzer"
postal_code = "3951en"
street_number = "1"

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
# street_number = "24"
# suffix = "C"

# provider = "rova"
# postal_code = "8021CC"
# street_number = "1"

# provider = "rmn"
# postal_code = "3402TA"
# street_number = "1"

# Ximmio
# provider = "meerlanden"
# postal_code = "2121xt"
# street_number = "38"

# Ximmio
# provider = "acv"
# postal_code = "6713CG"
# street_number = "11"

# postal_code = postal_code.strip().upper()

collector = MainCollector(
    provider,
    postal_code,
    street_number,
    suffix,
    exclude_pickup_today,
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
