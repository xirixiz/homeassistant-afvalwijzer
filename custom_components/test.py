from __future__ import annotations

import argparse
import json
import uuid
from typing import Any

import requests


BASE = "https://api.omrinafvalapp.nl"
LOGIN_URL = f"{BASE}/api/auth/login"
GQL_URL = f"{BASE}/graphql/"
TIMEOUT = (5.0, 30.0)


def format_zip(zip_code: str) -> str:
    z = (zip_code or "").replace(" ", "").upper().strip()
    return f"{z[:4]} {z[4:]}" if len(z) >= 6 else z


def login(session: requests.Session, zip_code: str, house_number: int, suffix: str, verify: bool) -> str:
    payload = {
        "Email": None,
        "Password": None,
        "PostalCode": format_zip(zip_code),
        "HouseNumber": int(house_number),
        "HouseNumberExtension": suffix or "",
        "DeviceId": str(uuid.uuid4()),
        "Platform": "HomeAssistant",
        "AppVersion": "6.0.0",
        "OsVersion": "Debian",
    }
    r = session.post(
        LOGIN_URL,
        json=payload,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Omrin.Afvalapp.Client/1.0",
        },
        timeout=TIMEOUT,
        verify=verify,
    )
    r.raise_for_status()
    data = r.json() if r.content else {}
    token = (data.get("data") or {}).get("accessToken") or data.get("accessToken") or data.get("token")
    if not token:
        raise RuntimeError(f"No token in login response: {data}")
    return str(token)


def gql(session: requests.Session, token: str, query: str, variables: dict[str, Any] | None, verify: bool) -> dict[str, Any]:
    r = session.post(
        GQL_URL,
        json={"query": query, "variables": variables or {}},
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "GraphQL.Client/6.1.0.0",
        },
        timeout=TIMEOUT,
        verify=verify,
    )
    r.raise_for_status()
    return r.json() if r.content else {}


def unwrap_named_type(t: dict[str, Any] | None) -> str | None:
    cur = t or {}
    while isinstance(cur, dict):
        if cur.get("name"):
            return str(cur["name"])
        cur = cur.get("ofType") or {}
    return None


def type_fields(session: requests.Session, token: str, type_name: str, verify: bool) -> list[str]:
    q = """
    query($name: String!) {
      __type(name: $name) {
        name
        fields { name type { kind name ofType { kind name ofType { kind name } } } }
      }
    }
    """
    data = gql(session, token, q, {"name": type_name}, verify=verify)
    t = (data.get("data") or {}).get("__type") or {}
    fields = t.get("fields") or []
    out = []
    for f in fields:
        if "name" in f:
            out.append(f["name"])
    return out


def type_fields_with_types(session: requests.Session, token: str, type_name: str, verify: bool) -> list[dict[str, Any]]:
    q = """
    query($name: String!) {
      __type(name: $name) {
        name
        fields {
          name
          type { kind name ofType { kind name ofType { kind name ofType { kind name } } } }
        }
      }
    }
    """
    data = gql(session, token, q, {"name": type_name}, verify=verify)
    t = (data.get("data") or {}).get("__type") or {}
    return t.get("fields") or []


def input_fields(session: requests.Session, token: str, input_name: str, verify: bool) -> list[dict[str, Any]]:
    q = """
    query($name: String!) {
      __type(name: $name) {
        name
        inputFields {
          name
          type { kind name ofType { kind name ofType { kind name ofType { kind name } } } }
        }
      }
    }
    """
    data = gql(session, token, q, {"name": input_name}, verify=verify)
    t = (data.get("data") or {}).get("__type") or {}
    return t.get("inputFields") or []


def query_field_type(session: requests.Session, token: str, field_name: str, verify: bool) -> tuple[str | None, list[dict[str, Any]]]:
    q = """
    query {
      __schema {
        queryType {
          fields {
            name
            type { kind name ofType { kind name ofType { kind name ofType { kind name } } } }
            args {
              name
              type { kind name ofType { kind name ofType { kind name ofType { kind name } } } }
            }
          }
        }
      }
    }
    """
    data = gql(session, token, q, None, verify=verify)
    fields = (((data.get("data") or {}).get("__schema") or {}).get("queryType") or {}).get("fields") or []
    for f in fields:
        if f.get("name") == field_name:
            return unwrap_named_type(f.get("type")), f.get("args") or []
    return None, []


def mutation_args(session: requests.Session, token: str, name: str, verify: bool) -> list[dict[str, Any]]:
    q = """
    query {
      __schema {
        mutationType {
          fields {
            name
            args { name type { kind name ofType { kind name ofType { kind name ofType { kind name } } } } }
          }
        }
      }
    }
    """
    data = gql(session, token, q, None, verify=verify)
    fields = (((data.get("data") or {}).get("__schema") or {}).get("mutationType") or {}).get("fields") or []
    for f in fields:
        if f.get("name") == name:
            return f.get("args") or []
    return []


def build_selection_for_object(session: requests.Session, token: str, type_name: str, verify: bool, depth: int = 1) -> str:
    """
    Build a safe selection set for an object type.
    depth 1 means include scalar fields only.
    depth 2 means include one level nested objects with their scalar fields.
    """
    fields = type_fields_with_types(session, token, type_name, verify)
    if not fields:
        return ""

    scalar_kinds = {"SCALAR", "ENUM"}
    pieces: list[str] = []

    for f in fields:
        name = f["name"]
        t = f.get("type") or {}
        leaf_name = unwrap_named_type(t)
        kind = t.get("kind")

        if kind in scalar_kinds:
            pieces.append(name)
            continue

        if depth >= 2 and leaf_name and leaf_name not in ("String", "Int", "Boolean", "Float", "ID"):
            nested = build_selection_for_object(session, token, leaf_name, verify, depth=1)
            if nested:
                pieces.append(f"{name} {{ {nested} }}")

    return "\n".join(pieces[:25])


def parse_calendar_items(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for it in items or []:
        d = it.get("date")
        t = it.get("type")
        if not d or not t:
            continue
        ds = str(d).strip()
        if len(ds) >= 10:
            ds = ds[:10]
        try:
            datetime.strptime(ds, "%Y-%m-%d")
        except ValueError:
            continue
        out.append({"type": str(t), "date": ds})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("postcode")
    ap.add_argument("housenumber")
    ap.add_argument("--suffix", default="")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()

    session = requests.Session()
    token = login(session, args.postcode, int(args.housenumber), args.suffix, verify=args.verify)
    print("Token length:", len(token))

    account_type, _ = query_field_type(session, token, "fetchMe", verify=args.verify)
    print("fetchMe return type:", account_type)

    if not account_type:
        raise SystemExit("Could not determine fetchMe return type")

    account_fields = type_fields(session, token, account_type, verify=args.verify)
    print("Account fields:", account_fields)

    address_type = None
    municipality_type = None

    if "address" in account_fields:
        address_type, _ = query_field_type(session, token, "fetchMe", verify=args.verify)
        # fetchMe type is Account. We need Address type by introspecting Account fields with types.
        acc_fields_t = type_fields_with_types(session, token, account_type, verify=args.verify)
        for f in acc_fields_t:
            if f["name"] == "address":
                address_type = unwrap_named_type(f.get("type") or {})
            if f["name"] == "municipality":
                municipality_type = unwrap_named_type(f.get("type") or {})

    print("Address type:", address_type)
    print("Municipality type:", municipality_type)

    acc_sel_parts = []
    if address_type:
        addr_sel = build_selection_for_object(session, token, address_type, verify=args.verify, depth=1)
        if addr_sel:
            acc_sel_parts.append(f"address {{ {addr_sel} }}")
        else:
            acc_sel_parts.append("address { __typename }")

    if municipality_type:
        mun_sel = build_selection_for_object(session, token, municipality_type, verify=args.verify, depth=1)
        if mun_sel:
            acc_sel_parts.append(f"municipality {{ {mun_sel} }}")
        else:
            acc_sel_parts.append("municipality { __typename }")

    # Try also account field if present
    if "account" in account_fields:
        # account field might be scalar or object
        acc_sel_parts.append("account { __typename }")

    # Always include typename so we can debug
    acc_sel_parts.append("__typename")

    fetchme_query = f"query {{ fetchMe {{ {' '.join(acc_sel_parts)} }} }}"
    print("fetchMe query:", fetchme_query)
    fetchme_resp = gql(session, token, fetchme_query, None, verify=args.verify)
    print("fetchMe response:")
    print(json.dumps(fetchme_resp, indent=2, ensure_ascii=False))

    # Prepare registerDevice input properly
    reg_args = mutation_args(session, token, "registerDevice", verify=args.verify)
    print("registerDevice args:", [a.get("name") for a in reg_args])

    if reg_args:
        # It is registerDevice(input: RegisterDeviceInput!)
        input_type = None
        for a in reg_args:
            if a.get("name") == "input":
                input_type = unwrap_named_type(a.get("type") or {})
        print("RegisterDevice input type:", input_type)

        input_obj: dict[str, Any] = {}
        if input_type:
            inf = input_fields(session, token, input_type, verify=args.verify)
            print("RegisterDeviceInput fields:", [f["name"] for f in inf])

            device_id = str(uuid.uuid4())

            # Fill common field names if they exist
            for f in inf:
                name = f["name"].lower()
                real_name = f["name"]
                if name in ("deviceid", "device_id"):
                    input_obj[real_name] = device_id
                elif name in ("platform",):
                    input_obj[real_name] = "HomeAssistant"
                elif name in ("appversion", "app_version"):
                    input_obj[real_name] = "6.0.0"
                elif name in ("osversion", "os_version"):
                    input_obj[real_name] = "Debian"
                elif name in ("pushtoken", "push_token", "token"):
                    input_obj[real_name] = ""
                elif name in ("locale", "language"):
                    input_obj[real_name] = "nl"
                elif name in ("notificationsenabled", "notifications_enabled"):
                    input_obj[real_name] = False

            # If still empty, set at least deviceId if schema has anything similar
            if not input_obj and inf:
                input_obj[inf[0]["name"]] = device_id

        reg_mut = """
        mutation RegisterDevice($input: RegisterDeviceInput!) {
          registerDevice(input: $input)
        }
        """
        print("registerDevice input object:", input_obj)
        reg_resp = gql(session, token, reg_mut, {"input": input_obj}, verify=args.verify)
        print("registerDevice response:")
        print(json.dumps(reg_resp, indent=2, ensure_ascii=False))

    # Finally try fetchCalendar again
    fetchcal_query = """
    query {
      fetchCalendar {
        id
        date
        description
        type
        containerType
        placingTime
        state
      }
    }
    """
    cal_resp = gql(session, token, fetchcal_query, None, verify=args.verify)
    items = ((cal_resp.get("data") or {}).get("fetchCalendar")) or []
    parsed = parse_calendar_items(items)

    print("fetchCalendar response:")
    print(json.dumps(cal_resp, indent=2, ensure_ascii=False))
    print("Parsed items:", len(parsed))
    print(json.dumps(parsed[:50], indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
