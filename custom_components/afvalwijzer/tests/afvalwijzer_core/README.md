# afvalwijzer-core

Core logic for fetching and processing Dutch waste collection schedules.

## Features
- Multiple collector backends (Afvalwijzer, OPZET-style)
- Normalized waste collection model
- Home Assistant friendly JSON output
- CLI runner for manual testing

## Usage (CLI)

```bash
python3 -m afvalwijzer_core.runner auto mijnafvalwijzer 5146EA 73 | jq .
python3 -m afvalwijzer_core.runner auto saver 4708ls 10 | jq .