from datetime import datetime
from typing import Any, Dict, List

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..const import COLLECTORS_OPZET
from ..model import WasteCollection
from .base import BaseCollector

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class OpzetCollector(BaseCollector):
    def __init__(
        self,
        *,
        provider: str,
        postal_code: str,
        street_number: str,
        suffix: str,
        waste_type_rename,
    ):
        if provider not in COLLECTORS_OPZET:
            raise ValueError(f"Invalid provider: {provider}")

        self.provider = provider
        self.base_url = COLLECTORS_OPZET[provider].rstrip("/")
        self.postal_code = postal_code.strip().replace(" ", "").upper()
        self.street_number = str(street_number).strip()
        self.suffix = (suffix or "").strip().upper()
        self.waste_type_rename = waste_type_rename

    def fetch_raw(self) -> Dict[str, Any]:
        url_address = (
            f"{self.base_url}/rest/adressen/{self.postal_code}-{self.street_number}"
        )
        r_addr = requests.get(url_address, timeout=60, verify=False)
        r_addr.raise_for_status()
        addresses = r_addr.json()
        if not addresses:
            raise KeyError("No address results returned")

        bag_id = self._select_bag_id(addresses, self.suffix)

        url_waste = f"{self.base_url}/rest/adressen/{bag_id}/afvalstromen"
        r_waste = requests.get(url_waste, timeout=60, verify=False)
        r_waste.raise_for_status()
        streams = r_waste.json()

        return {"bag_id": bag_id, "streams": streams}

    def parse(self, raw: Dict[str, Any]) -> List[WasteCollection]:
        streams = raw.get("streams") or []
        out: List[WasteCollection] = []
        for item in streams:
            pickup = item.get("ophaaldatum")
            if not pickup:
                continue

            menu_title = (item.get("menu_title") or "").strip().lower()
            wt = self.waste_type_rename(menu_title)
            if not wt:
                continue

            pickup_day = datetime.strptime(pickup, "%Y-%m-%d").date()
            out.append(WasteCollection.from_any(pickup_day, wt))

        return out

    @staticmethod
    def _select_bag_id(addresses: List[Dict[str, Any]], suffix: str) -> str:
        if len(addresses) > 1 and suffix:
            for item in addresses:
                if (
                    item.get("huisletter") == suffix
                    or item.get("huisnummerToevoeging") == suffix
                ):
                    bag = item.get("bagId")
                    if bag:
                        return bag

        bag = addresses[0].get("bagId")
        if not bag:
            raise KeyError("bagId missing from address response")
        return bag
