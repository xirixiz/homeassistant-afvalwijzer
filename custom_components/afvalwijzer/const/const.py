"""Afvalwijzer integration."""

from datetime import timedelta
import logging

_LOGGER = logging.getLogger(__name__)

API = "api"
NAME = "afvalwijzer"
VERSION = "2026.1007"

ISSUE_URL = "https://github.com/xirixiz/homeassistant-afvalwijzer/issues"

SENSOR_COLLECTORS_AFVALALERT = {
    "afvalalert": "https://www.afvalalert.nl/kalender",
}

SENSOR_COLLECTORS_AMSTERDAM = {
    "amsterdam": "https://api.data.amsterdam.nl/v1/afvalwijzer/afvalwijzer",
}

SENSOR_COLLECTORS_LIMBURG_NET = {
    "limburg_net": {"city": "Hasselt", "street": "Kerkstraat"},
    "LIMBURG_NET": {"city": "Hasselt", "street": "Kerkstraat"},
}

SENSOR_COLLECTORS_MIJNAFVALWIJZER = {
    "mijnafvalwijzer": "https://api.mijnafvalwijzer.nl/webservices/appsinput/?apikey=5ef443e778f41c4f75c69459eea6e6ae0c2d92de729aa0fc61653815fbd6a8ca&method=postcodecheck&postcode={0}&street=&huisnummer={1}&toevoeging={2}&app_name=afvalwijzer&platform=web&langs=nl",
}

SENSOR_COLLECTORS_MONTFERLAND = {
    "montferland": "http://afvalwijzer.afvaloverzicht.nl",
}

SENSOR_COLLECTORS_STRAATBEELD = {
    "straatbeeld": "https://drimmelen.api.straatbeeld.online",
}

SENSOR_COLLECTORS_RECYCLEAPP = {
    "recycleapp": "https://www.recycleapp.be/api/app/v1/",
}

SENSOR_COLLECTORS_BURGERPORTAAL = {
    "assen": "138204213565303512",
    "bar": "138204213564933497",
    "groningen": "452048812597326549",
    "nijkerk": "138204213565304094",
    "rmn": "138204213564933597",
    "tilburg": "452048812597339353",
}

SENSOR_COLLECTORS_CIRCULUS = {
    "circulus": "https://mijn.circulus.nl",
}

SENSOR_COLLECTORS_DEAFVALAPP = {
    "deafvalapp": "https://dataservice.deafvalapp.nl/dataservice/DataServiceServlet?service=OPHAALSCHEMA&land=NL&postcode={0}&straatId=0&huisnr={1}&huisnrtoev={2}",
}

SENSOR_COLLECTORS_IRADO = {
    "irado": "https://www.irado.nl/wp-json/wsa/v1/location/address/calendar/pickups?zipcode={0}&number={1}&extention={2}",
}

SENSOR_COLLECTORS_KLIKOGROEP = {
    "oudeijsselstreek": {
        "id": "454",
        "url": "cp-oudeijsselstreek.klikocontainermanager.com",
    },
    "maassluis": {
        "id": "505",
        "url": "cp-maassluis.klikocontainermanager.com",
    },
}

SENSOR_COLLECTORS_OMRIN = {
    "omrin": "https://api.omrinafvalapp.nl",
}

SENSOR_COLLECTORS_OPZET = {
    "afval3xbeter": "https://afval3xbeter.nl",
    "afvalstoffendienst": "https://afvalstoffendienst.nl",
    "afvalstoffendienstkalender": "https://afvalstoffendienst.nl",
    "alphenaandenrijn": "https://afvalkalender.alphenaandenrijn.nl",
    "berkelland": "https://afvalkalender.gemeenteberkelland.nl",
    "cranendonck": "https://afvalkalender.cranendonck.nl",
    "cyclus": "https://cyclusnv.nl",
    "dar": "https://afvalkalender.dar.nl",
    "defryskemarren": "https://afvalkalender.defryskemarren.nl",
    "denhaag": "https://huisvuilkalender.denhaag.nl",
    "gad": "https://inzamelkalender.gad.nl",
    "geertruidenberg": "https://afval.geertruidenberg.nl",
    "hvc": "https://inzamelkalender.hvcgroep.nl",
    "lingewaard": "https://afvalwijzer.lingewaard.nl",
    "middelburg-vlissingen": "https://afvalwijzer.middelburgvlissingen.nl",
    "mijnafvalzaken": "https://mijnafvalzaken.nl",
    "montfoort": "https://cyclusnv.nl",
    "offalkalinder": "https://www.offalkalinder.nl",
    "peelenmaas": "https://afvalkalender.peelenmaas.nl",
    "prezero": "https://inzamelwijzer.prezero.nl",
    "purmerend": "https://afvalkalender.purmerend.nl",
    "rwm": "https://rwm.nl",
    "saver": "https://saver.nl",
    "schouwen-duiveland": "https://afvalkalender.schouwen-duiveland.nl",
    "sliedrecht": "https://afvalkalender.sliedrecht.nl",
    "spaarnelanden": "https://afvalwijzer.spaarnelanden.nl",
    "sudwestfryslan": "https://afvalkalender.sudwestfryslan.nl",
    "suez": "https://inzamelwijzer.prezero.nl",
    "uithoorn": "https://cyclusnv.nl",
    "venray": "https://afvalkalender.venray.nl",
    "voorschoten": "https://afvalkalender.voorschoten.nl",
    "waalre": "https://afvalkalender.waalre.nl",
    "zrd": "https://www.zrd.nl",
}

SENSOR_COLLECTORS_RD4 = {
    "rd4": "https://data.rd4.nl/api/v1/waste-calendar?postal_code={0}&house_number={1}&house_number_extension={2}&year={3}",
}

SENSOR_COLLECTORS_REINIS = {
    "reinis": "https://reinis.nl",
}

SENSOR_COLLECTORS_RWM = {
    "getAddress": "https://rwm.nl/adressen/{0}:{1}",
    "getSchedule": "https://rwm.nl/rest/adressen/{0}/afvalstromen",
}

SENSOR_COLLECTORS_ROVA = {
    "rova": "https://www.rova.nl",
}

SENSOR_COLLECTORS_XIMMIO = {
    "avalex": "https://wasteprod2api.ximmio.com",
    "blink": "https://wasteprod2api.ximmio.com",
    "meerlanden": "https://wasteprod2api.ximmio.com",
    "rad": "https://wasteprod2api.ximmio.com",
    "westland": "https://wasteprod2api.ximmio.com",
    "woerden": "https://wasteprod2api.ximmio.com",
    "ximmio": "https://wasteapi.ximmio.com",
}

SENSOR_COLLECTORS_XIMMIO_IDS = {
    "acv": "f8e2844a-095e-48f9-9f98-71fceb51d2c3",
    "almere": "53d8db94-7945-42fd-9742-9bbc71dbe4c1",
    "areareiniging": "adc418da-d19b-11e5-ab30-625662870761",
    "avalex": "f7a74ad1-fdbf-4a43-9f91-44644f4d4222",
    "avri": "78cd4156-394b-413d-8936-d407e334559a",
    "blink": "252d30d0-2e74-469c-8f1e-c0e2e434eb58",
    "hellendoorn": "24434f5b-7244-412b-9306-3a2bd1e22bc1",
    "meerlanden": "800bf8d7-6dd1-4490-ba9d-b419d6dc8a45",
    "rad": "13a2cad9-36d0-4b01-b877-efcb421a864d",
    "twentemilieu": "8d97bb56-5afd-4cbc-a651-b4f7314264b4",
    "venlo": "280affe9-1428-443b-895a-b90431b8ca31",
    "waardlanden": "942abcf6-3775-400d-ae5d-7380d728b23c",
    "westland": "6fc75608-126a-4a50-9241-a002ce8c8a6c",
    "woerden": "06856f74-6826-4c6a-aabf-69bc9d20b5a6",
    "ximmio": "800bf8d7-6dd1-4490-ba9d-b419d6dc8a45",
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

SCAN_INTERVAL = timedelta(hours=4)

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
