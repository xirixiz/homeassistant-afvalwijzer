#!/usr/bin/env python3

from datetime import date
import json
import pathlib
import re

version = date.today().strftime("%Y.%m.%d")

manifest_path = pathlib.Path("custom_components/afvalwijzer/manifest.json")
const_path = pathlib.Path("custom_components/afvalwijzer/const/const.py")

# update manifest.json
with manifest_path.open("r", encoding="utf-8") as f:
    manifest = json.load(f)

manifest["version"] = version

with manifest_path.open("w", encoding="utf-8") as f:
    json.dump(manifest, f, indent=2)
    f.write("\n")

# update const.py
const_text = const_path.read_text(encoding="utf-8")
const_text = re.sub(
    r'VERSION\s*=\s*"[0-9.]+"',
    f'VERSION = "{version}"',
    const_text,
)

const_path.write_text(const_text, encoding="utf-8")

print("Updated version to", version)

