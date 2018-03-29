#!/usr/bin/env python
"""
@ Author      : Bram van Dartel
@ Date        : 28/03/2018
@ Description : MijnAfvalwijzer to JSON
"""

import requests
import json
import argparse
import datetime

def get_args():
    parser = argparse.ArgumentParser(
        description='MijnAfvalwijzer JSON parser for Home Assistant.')
    parser.add_argument(
        '-p', '--postcode', type=str, help='Postcode', required=True)
    parser.add_argument(
        '-n', '--huisnummer', type=str, help='Huisnummer', required=True)
    parser.add_argument(
        '-t', '--toevoeging', type=str, help='Toevoeging', required=False, default="")
    args = parser.parse_args()
    postcode = args.postcode
    huisnummer = args.huisnummer
    toevoeging = args.toevoeging
    return postcode, huisnummer, toevoeging

postcode, huisnummer, toevoeging = get_args()

url = ("http://json.mijnafvalwijzer.nl/?"
       "method=postcodecheck&postcode={0}&street=&huisnummer={1}&toevoeging={2}&platform=phone&langs=nl&").format(postcode,huisnummer,toevoeging)
response = requests.get(url)
json_obj = response.json()
json_data = json_obj['data']['ophaaldagen']['data']
json_data_next = json_obj['data']['ophaaldagenNext']['data']

trashType = {}
trashDate = {}
trashTotal = {}

# Collect legend
for item in json_data:
    name = item["nameType"]
    if name not in trashType:
        trashType[name] = item["nameType"]

# Collect days
for item in json_data:
    d = datetime.datetime.strptime(item['date'], "%Y-%m-%d")
    dateConvert = d.strftime("%d/%m/%Y")
    if dateConvert not in trashDate:
        trashDate[dateConvert] = item["nameType"]

# Beautify
trashType = {"legend": trashType}
trashDate = {"days": trashDate}
trashTotal.update(trashType)
trashTotal.update(trashDate)

print(json.dumps(trashTotal, indent=4))
