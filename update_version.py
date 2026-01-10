#!/usr/bin/env python3

from datetime import date
import json
import pathlib
import re

manifest_path = pathlib.Path("custom_components/afvalwijzer/manifest.json")
const_path = pathlib.Path("custom_components/afvalwijzer/const/const.py")

VERSION_RE = re.compile(r"^(?P<year>\d{4})\.(?P<seq>\d{4,})$")


def compute_next_version(current_version: str | None) -> str:
    current_year = date.today().year

    if current_version:
        m = VERSION_RE.match(current_version.strip())
        if m:
            stored_year = int(m.group("year"))
            stored_seq = int(m.group("seq"))

            if stored_year == current_year:
                return f"{current_year}.{stored_seq + 1}"
            else:
                return f"{current_year}.1000"

    return f"{current_year}.1000"


# read current version from manifest.json (source of truth)
with manifest_path.open("r", encoding="utf-8") as f:
    manifest = json.load(f)

old_version = str(manifest.get("version", "")).strip() or None
new_version = compute_next_version(old_version)

# update manifest.json
manifest["version"] = new_version
with manifest_path.open("w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)
    f.write("\n")

# update const.py
const_text = const_path.read_text(encoding="utf-8")

if re.search(r'VERSION\s*=\s*"[0-9.]+"', const_text):
    const_text = re.sub(
        r'VERSION\s*=\s*"[0-9.]+"',
        f'VERSION = "{new_version}"',
        const_text,
    )
else:
    # optional: add VERSION if it does not exist
    const_text = const_text.rstrip() + f'\n\nVERSION = "{new_version}"\n'

const_path.write_text(const_text, encoding="utf-8")

print("Updated version from", old_version, "to", new_version)
