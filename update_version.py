#!/usr/bin/env python3
"""Update the Afvalwijzer integration version."""

from datetime import date
import json
from pathlib import Path
import re

MANIFEST_PATH = Path("custom_components/afvalwijzer/manifest.json")
CONST_PATH = Path("custom_components/afvalwijzer/const/const.py")

VERSION_RE = re.compile(r"^(?P<year>\d{4})\.(?P<seq>\d{4,})$")
VERSION_ASSIGN_RE = re.compile(r'VERSION\s*=\s*"(?P<version>[0-9.]+)"')


def compute_next_version(current_version: str | None) -> str:
    """Compute the next version string based on the current date and version."""
    current_year = date.today().year

    if current_version:
        match = VERSION_RE.match(current_version.strip())
        if match:
            stored_year = int(match.group("year"))
            stored_seq = int(match.group("seq"))

            if stored_year == current_year:
                return f"{current_year}.{stored_seq + 1}"
            return f"{current_year}.1000"

    return f"{current_year}.1000"


def main() -> None:
    """Update version numbers in manifest.json and const.py."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    old_version = str(manifest.get("version", "")).strip() or None
    new_version = compute_next_version(old_version)

    if manifest.get("version") != new_version:
        manifest["version"] = new_version
        MANIFEST_PATH.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    const_text = CONST_PATH.read_text(encoding="utf-8")

    if VERSION_ASSIGN_RE.search(const_text):
        new_const_text = VERSION_ASSIGN_RE.sub(
            f'VERSION = "{new_version}"', const_text
        )
    else:
        new_const_text = const_text.rstrip() + f'\n\nVERSION = "{new_version}"\n'

    if new_const_text != const_text:
        CONST_PATH.write_text(new_const_text, encoding="utf-8")


if __name__ == "__main__":
    main()
