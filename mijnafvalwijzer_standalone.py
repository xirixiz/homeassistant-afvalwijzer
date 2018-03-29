#!/usr/bin/env python
"""
@ Author      : Bram van Dartel
@ Date        : 28/03/2018
@ Description : MijnAfvalwijzer to JSON
"""

from urllib.request import urlopen
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
response = urlopen(url)
string = response.read().decode('utf-8')
json_obj = json.loads(string)
json_data = json_obj['data']['ophaaldagen']['data']
json_data_next = json_obj['data']['ophaaldagenNext']['data']
today = datetime.date.today().strftime("%Y-%m-%d")
trashType = {}
trashTotal = []
countType = 1

# Collect legend
for item in json_data or json_data_next:
    name = item["nameType"]
    if name not in trashType:
            trash = {}
            trashType[name] = item["nameType"]
            trash[countType] = item["nameType"]
            countType +=1
            trashTotal.append(trash)

print(trashTotal)

trashType = {}
trashTotal = []

# Collect legend
for item in json_data or json_data_next:
    name = item["nameType"]
    d = datetime.datetime.strptime(item['date'], "%Y-%m-%d")
    dateConvert = d.strftime("%Y-%m-%d")
    if name not in trashType:
        if item['date'] > today:
            trash = {}
            trashType[name] = item["nameType"]
            trash["name_type"] = item["nameType"]
            trash["pickup_date"] = dateConvert
            trashTotal.append(trash)

print(trashTotal)
