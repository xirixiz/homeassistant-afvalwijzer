"""Check that all collector endpoints pass TLS certificate verification.

Run from the repository root:

    python3 scripts/test_tls.py

Only the base URL of each endpoint is requested; 404s and timeouts are
ignored since we only care about certificate validation errors.
"""

from urllib.parse import urlparse

import requests

from custom_components.afvalwijzer.const import const

# Gather all dictionary variables that start with SENSOR_COLLECTORS_
urls = set()
for var_name in dir(const):
    if var_name.startswith("SENSOR_COLLECTORS_"):
        obj = getattr(const, var_name)
        if isinstance(obj, dict):
            for value in obj.values():
                if isinstance(value, str) and value.startswith("https"):
                    # Extract base URL to avoid 404s/400s as much as possible
                    parsed = urlparse(value)
                    urls.add(f"{parsed.scheme}://{parsed.netloc}")

# Also test KLIKOGROEP endpoints, which are stored slightly differently
for data in const.SENSOR_COLLECTORS_KLIKOGROEP.values():
    urls.add(f"https://{data['url']}")

print(f"Testing {len(urls)} unique base URLs for TLS validation...")

failed = []
for url in sorted(urls):
    try:
        requests.get(url, verify=True, timeout=5)
        print(f"[OK] {url}")
    except requests.exceptions.SSLError as err:
        print(f"[SSL ERROR] {url}: {err}")
        failed.append(url)
    except requests.exceptions.RequestException as err:
        # Ignore 404s, timeouts, etc; we only care about SSL errors
        print(f"[OTHER ERROR] {url}: {err}")

print("\n--- Summary ---")
if not failed:
    print("All endpoints passed TLS verification!")
else:
    print(f"Failed TLS verification on {len(failed)} endpoints:")
    for url in failed:
        print(f" - {url}")
