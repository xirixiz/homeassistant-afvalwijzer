from datetime import timedelta
import logging

_LOGGER = logging.getLogger(__name__)

API = "api"
NAME = "afvalwijzer"
VERSION = "2024.06.02"

ISSUE_URL = "https://github.com/xirixiz/homeassistant-afvalwijzer/issues"

SENSOR_COLLECTOR_TO_URL = {
    "afvalwijzer_data_default": [
        "https://api.{0}.nl/webservices/appsinput/?apikey=5ef443e778f41c4f75c69459eea6e6ae0c2d92de729aa0fc61653815fbd6a8ca&method=postcodecheck&postcode={1}&street=&huisnummer={2}&toevoeging={3}&app_name=afvalwijzer&platform=web&afvaldata={4}&langs=nl&"
    ],
    "afvalstoffendienstkalender": [
        "https://{0}.afvalstoffendienstkalender.nl/nl/{1}/{2}/"
    ],
    "afvalstoffendienstkalender-s-hertogenbosch": [
        "https://afvalstoffendienstkalender.nl/nl/{0}/{1}/"
    ],
    "ximmio01": [
        "https://wasteapi.ximmio.com/api/FetchAdress",
        "https://wasteapi.ximmio.com/api/GetCalendar",
    ],
    "ximmio02": [
        "https://wasteprod2api.ximmio.com/api/FetchAdress",
        "https://wasteprod2api.ximmio.com/api/GetCalendar",
    ],
}

SENSOR_COLLECTORS_OPZET = {
    "alkmaar": "https://www.stadswerk072.nl",
    "alphenaandenrijn": "https://afvalkalender.alphenaandenrijn.nl",
    "berkelland": "https://afvalkalender.gemeenteberkelland.nl",
    "blink": "https://mijnblink.nl",
    "cranendonck": "https://afvalkalender.cranendonck.nl",
    "cyclus": "https://afvalkalender.cyclusnv.nl",
    "dar": "https://afvalkalender.dar.nl",
    "denhaag": "https://huisvuilkalender.denhaag.nl",
    "gad": "https://inzamelkalender.gad.nl",
    "hvc": "https://inzamelkalender.hvcgroep.nl",
    "lingewaard": "https://afvalwijzer.lingewaard.nl",
    "middelburg-vlissingen": "https://afvalwijzer.middelburgvlissingen.nl",
    "montfoort": "https://afvalkalender.cyclusnv.nl",
    "peelenmaas": "https://afvalkalender.peelenmaas.nl",
    "prezero": "https://inzamelwijzer.prezero.nl",
    "purmerend": "https://afvalkalender.purmerend.nl",
    "schouwen-duiveland": "https://afvalkalender.schouwen-duiveland.nl",
    "spaarnelanden": "https://afvalwijzer.spaarnelanden.nl",
    "sudwestfryslan": "https://afvalkalender.sudwestfryslan.nl",
    "suez": "https://inzamelwijzer.prezero.nl",
    "venray": "https://afvalkalender.venray.nl",
    "voorschoten": "https://afvalkalender.voorschoten.nl",
    "waalre": "https://afvalkalender.waalre.nl",
    "zrd": "https://www.zrd.nl",
}

SENSOR_COLLECTORS_ICALENDAR = {
    "eemsdelta": "https://www.eemsdelta.nl/trash-calendar/download/{1}/{2}",
    "veldhoven": "https://www.veldhoven.nl/afvalkalender/{5}/{1}-{2}.ics",
}

SENSOR_COLLECTORS_AFVALWIJZER = [
    "mijnafvalwijzer",
    "afvalstoffendienstkalender",
    "afvalstoffendienstkalender-s-hertogenbosch",
    "rova",
]

SENSOR_COLLECTORS_XIMMIO = {
    "acv": "f8e2844a-095e-48f9-9f98-71fceb51d2c3",
    "almere": "53d8db94-7945-42fd-9742-9bbc71dbe4c1",
    "areareiniging": "adc418da-d19b-11e5-ab30-625662870761",
    "avalex": "f7a74ad1-fdbf-4a43-9f91-44644f4d4222",
    "avri": "78cd4156-394b-413d-8936-d407e334559a",
    "hellendoorn": "24434f5b-7244-412b-9306-3a2bd1e22bc1",
    "meerlanden": "800bf8d7-6dd1-4490-ba9d-b419d6dc8a45",
    "meppel": "b7a594c7-2490-4413-88f9-94749a3ec62a",
    "rad": "13a2cad9-36d0-4b01-b877-efcb421a864d",
    "twentemilieu": "8d97bb56-5afd-4cbc-a651-b4f7314264b4",
    "waardlanden": "942abcf6-3775-400d-ae5d-7380d728b23c",
    "westland": "6fc75608-126a-4a50-9241-a002ce8c8a6c",
    "ximmio": "800bf8d7-6dd1-4490-ba9d-b419d6dc8a45",
    "reinis": "9dc25c8a-175a-4a41-b7a1-83f237a80b77",
    "woerden": "06856f74-6826-4c6a-aabf-69bc9d20b5a6",
}

SENSOR_COLLECTORS_RD4 = {
    "rd4": "https://data.rd4.nl/api/v1/waste-calendar?postal_code={0}&house_number={1}&house_number_extension={2}&year={3}",
}

SENSOR_COLLECTORS_CIRCULUS = {
    "circulus": "https://mijn.circulus.nl",
}

SENSOR_COLLECTORS_BURGERPORTAAL = {
    'rmn': '138204213564933597',
    'bar': '138204213564933497',
    'assen': '138204213565303512',
    'nijkerk': '138204213565304094',
}

SENSOR_COLLECTORS_DEAFVALAPP = {
    "deafvalapp": "https://dataservice.deafvalapp.nl/dataservice/DataServiceServlet?service=OPHAALSCHEMA&land=NL&postcode={0}&straatId=0&huisnr={1}&huisnrtoev={2}",
}

SENSOR_COLLECTORS_RWM = {
    "getAddress": "https://rwm.nl/adressen/{0}:{1}",
    "getSchedule": "https://rwm.nl/rest/adressen/{0}/afvalstromen"
}

CONF_COLLECTOR = "provider"
CONF_API_TOKEN = "api_token"
CONF_POSTAL_CODE = "postal_code"
CONF_STREET_NUMBER = "street_number"
CONF_SUFFIX = "suffix"
CONF_DATE_FORMAT = "date_format"
CONF_EXCLUDE_PICKUP_TODAY = "exclude_pickup_today"
CONF_DEFAULT_LABEL = "default_label"
CONF_ID = "id"
CONF_EXCLUDE_LIST = "exclude_list"
CONF_DATE_ISOFORMAT = "date_isoformat"

SENSOR_PREFIX = "afvalwijzer "
SENSOR_ICON = "mdi:recycle"

ATTR_LAST_UPDATE = "last_update"
ATTR_IS_COLLECTION_DATE_TODAY = "is_collection_date_today"
ATTR_IS_COLLECTION_DATE_TOMORROW = "is_collection_date_tomorrow"
ATTR_IS_COLLECTION_DATE_DAY_AFTER_TOMORROW = "is_collection_date_day_after_tomorrow"
ATTR_DAYS_UNTIL_COLLECTION_DATE = "days_until_collection_date"

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)
PARALLEL_UPDATES = 1
SCAN_INTERVAL = timedelta(seconds=30)

DOMAIN = "afvalwijzer"
DOMAIN_DATA = "afvalwijzer_data"

STARTUP_MESSAGE = f"""
-------------------------------------------------------------------,
Afvalwijzer - {VERSION},
This is a custom integration!,
If you have any issues with this you need to open an issue here:,
https://github.com/xirixiz/homeassistant-afvalwijzer/issues,
-------------------------------------------------------------------,
"""
