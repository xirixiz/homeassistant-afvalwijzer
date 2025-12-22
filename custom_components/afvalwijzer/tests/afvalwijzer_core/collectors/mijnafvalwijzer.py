from datetime import date
from typing import Any, Dict, List, Callable, Optional

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..const import MIJNAFVALWIJZER_API_KEY, COLLECTORS_MIJNAFVALWIJZER
from ..model import WasteCollection
from .base import BaseCollector

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)


class MijnAfvalwijzerCollector(BaseCollector):
    def __init__(
        self,
        *,
        provider: str,
        postal_code: str,
        street_number: str,
        suffix: str,
        waste_type_rename: Callable[[str], Optional[str]],
    ):
        if provider not in COLLECTORS_MIJNAFVALWIJZER:
            raise ValueError(f"Invalid provider: {provider}")

        self.provider = provider
        self.base_url = COLLECTORS_MIJNAFVALWIJZER[provider].rstrip("/")
        self.postal_code = postal_code.strip().replace(" ", "").upper()
        self.street_number = str(street_number).strip()
        self.suffix = (suffix or "").strip().upper()
        self.waste_type_rename = waste_type_rename

    def fetch_raw(self) -> Dict[str, Any]:
        url = (
            f"{self.base_url}/webservices/appsinput/"
            f"?apikey={MIJNAFVALWIJZER_API_KEY}"
            f"&method=postcodecheck"
            f"&postcode={self.postal_code}"
            f"&street="
            f"&huisnummer={self.street_number}"
            f"&toevoeging={self.suffix}"
            f"&app_name=afvalwijzer"
            f"&platform=web"
            f"&afvaldata={date.today().isoformat()}"
            f"&langs=nl&"
        )
        r = requests.get(url, timeout=60, verify=False)
        r.raise_for_status()
        return r.json()

    def parse(self, raw: Dict[str, Any]) -> List[WasteCollection]:
        part1 = raw.get("ophaaldagen", {}).get("data", []) or []
        part2 = raw.get("ophaaldagenNext", {}).get("data", []) or []
        if not part1 and not part2:
            raise KeyError("No pickup data returned")

        out: List[WasteCollection] = []
        for entry in (part1 + part2):
            waste_type = self.waste_type_rename(entry["type"])
            if not waste_type:
                continue
            out.append(WasteCollection.from_any(entry["date"], waste_type))

        return out
