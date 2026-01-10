import json
import logging
import sys

from .collectors.factory import make_collector
from .repository import WasteCollectionRepository


def waste_type_rename(raw: str) -> str | None:
    s = (raw or "").strip().lower()
    if not s:
        return None
    return s


def usage() -> None:
    print(
        "Usage: python -m afvalwijzer_core.runner <family> <provider> <postal_code> <street_number> [suffix]"
    )
    print("family: auto | afvalwijzer | opzet")


def main(argv) -> int:
    logging.basicConfig(level=logging.INFO)

    if len(argv) < 5 or len(argv) > 6:
        usage()
        return 1

    from .core import build_ha_json

    family, provider, postal_code, street_number = argv[1:5]
    suffix = argv[5] if len(argv) == 6 else ""

    try:
        collector = make_collector(
            family=family,
            provider=provider,
            postal_code=postal_code,
            street_number=street_number,
            suffix=suffix,
            waste_type_rename=waste_type_rename,
        )
        items = collector.collect()

        repo = WasteCollectionRepository(items)
        out = build_ha_json(repo)

        print(json.dumps(out, ensure_ascii=False))
        return 0

    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
