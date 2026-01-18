"""Afvalwijzer integration."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
import re
import uuid

import requests
from urllib3.exceptions import InsecureRequestWarning

from ..common.main_functions import format_postal_code_omrin, waste_type_rename
from ..const.const import _LOGGER, SENSOR_COLLECTORS_OMRIN

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

_DEFAULT_TIMEOUT: tuple[float, float] = (5.0, 30.0)

# --- PDF parsing deps (prefer pdfplumber; fallback to pypdf) ---
try:
    import pdfplumber  # type: ignore
except Exception:  # pragma: no cover
    pdfplumber = None  # type: ignore

try:
    from pypdf import PdfReader  # type: ignore
except Exception:  # pragma: no cover
    PdfReader = None  # type: ignore


def _build_url(provider: str, postal_code: str, street_number: str, suffix: str) -> str:
    if provider not in SENSOR_COLLECTORS_OMRIN:
        raise ValueError(f"Invalid provider: {provider}, please verify")

    corrected_postal_code = format_postal_code_omrin(postal_code)

    return SENSOR_COLLECTORS_OMRIN[provider].format(
        corrected_postal_code,
        street_number,
        suffix,
    )


def _normalize_token(token: str | None) -> str | None:
    """Allow passing either a raw token or 'Bearer <token>'."""
    if not token:
        return None
    token = token.strip()
    if not token:
        return None
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token or None


def _login(
    session: requests.Session,
    url: str,
    postal_code: str,
    street_number: str,
    suffix: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
    device_id: str | None = None,
) -> str:
    """
    Kept for compatibility with existing config/usage.
    Omrin seems to have changed/blocked the old flow; we now parse the PDF endpoint instead.
    """
    payload = {
        "Email": None,
        "Password": None,
        # keep original behavior: use raw input postal_code here
        "PostalCode": postal_code,
        "HouseNumber": int(street_number),
        "HouseNumberExtension": suffix,
        "DeviceId": device_id or str(uuid.uuid4()),
        "Platform": "HomeAssistant",
        "AppVersion": "4.0.3.273",
        "OsVersion": "HomeAssistant 2024.1",
    }

    response = session.post(
        f"{url}/api/auth/login",
        json=payload,
        headers={
            "User-Agent": "Omrin.Afvalapp.Client/1.0",
            "Accept": "application/json",
        },
        timeout=timeout,
        verify=verify,
    )
    response.raise_for_status()

    data = response.json() if response.content else {}
    if not (data.get("success") and data.get("data")):
        raise ValueError(f"Login failed: {data.get('errors', 'Unknown error')}")

    token = (data.get("data") or {}).get("accessToken")
    if not token:
        raise ValueError("Not logged in")

    return token


def _fetch_calendar(
    session: requests.Session,
    url: str,
    token: str,
    *,
    timeout: tuple[float, float],
    verify: bool,
) -> Sequence[dict[str, Any]]:
    """
    Kept signature/name for minimal churn, but no longer uses GraphQL.
    The caller now provides 'token' as a carrier for the year (string/int) if needed,
    otherwise we default to current year.

    Returns: [{"date": "YYYY-MM-DD", "type": "<raw label>"}]
    """
    # token is ignored as auth, but kept to avoid breaking call sites.
    # If someone passed token="2026", we treat that as year override.
    year = datetime.now().year
    try:
        year = int(str(token).strip())
    except Exception:
        pass

    # url is expected to be something like "https://www.omrin.nl" (depends on your mapping)
    # Build the new PDF endpoint URL:
    # https://www.omrin.nl/api/CalendarPdf?zipCode=8085%20RT&houseNumber=11&year=2026
    #
    # We do NOT have postal_code/houseNumber here (signature kept), so get_waste_data_raw
    # now calls the PDF fetcher directly (see below).
    raise RuntimeError("Internal: _fetch_calendar should not be called directly anymore")


def _extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    if PdfReader is None:
        return ""
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))  # type: ignore[name-defined]
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:
        return ""


def _parse_calendar_pdf(
    pdf_bytes: bytes,
    *,
    year: int,
) -> list[dict[str, Any]]:
    """
    Parse the Omrin CalendarPdf into [{"date": "YYYY-MM-DD", "type": "<raw label>"}]
    so _parse_waste_data_raw stays unchanged.

    Generic:
    - Detects month columns (JAN..DEC)
    - Detects table rows by layout (left label column), without hardcoded row names
    - Builds row labels by taking words until the first day-number token in that line
    - Keeps only rows that actually contain day numbers in month columns
    - Also parses "Ophaaldata: dd/mm, ..." blocks and uses the nearest section header as type
    """
    out: list[dict[str, Any]] = []

    month_map = {
        "JAN": 1,
        "FEB": 2,
        "MRT": 3,
        "APR": 4,
        "MEI": 5,
        "JUNI": 6,
        "JULI": 7,
        "AUG": 8,
        "SEPT": 9,
        "OKT": 10,
        "NOV": 11,
        "DEC": 12,
    }
    month_set = set(month_map.keys())

    if pdfplumber is None:
        # Without pdfplumber we can't do robust layout parsing.
        # We keep at least the "Ophaaldata:" fallback using extracted text if available.
        text_all = ""
        try:
            if PdfReader is not None:
                import io
                reader = PdfReader(io.BytesIO(pdf_bytes))
                text_all = "\n".join((p.extract_text() or "") for p in reader.pages)
        except Exception:
            text_all = ""

        # Very basic generic "Ophaaldata:" fallback (no section header association)
        m = re.search(r"Ophaaldata:\s*([0-9/,\s]+)\.", text_all, flags=re.IGNORECASE)
        if m:
            raw = m.group(1)
            for part in raw.split(","):
                part = part.strip()
                dm = re.fullmatch(r"(\d{1,2})/(\d{1,2})", part)
                if not dm:
                    continue
                day = int(dm.group(1))
                month = int(dm.group(2))
                try:
                    d = datetime(year, month, day).strftime("%Y-%m-%d")
                except ValueError:
                    continue
                out.append({"type": "ophaaldata", "date": d})

        # dedupe
        seen = set()
        deduped: list[dict[str, Any]] = []
        for item in out:
            key = (item.get("type"), item.get("date"))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    def _is_day_token(txt: str) -> bool:
        return bool(re.fullmatch(r"\d{1,2}(\*)?", txt.strip()))

    def _has_letters(txt: str) -> bool:
        return bool(re.search(r"[A-Za-zÀ-ÿ]", txt))

    def _clean_row_label(label: str) -> str:
        parts = [p for p in re.split(r"\s+", label.strip()) if p]
        cleaned: list[str] = []
        prev = None
        for p in parts:
            pl = p.lower()
            if pl == prev:
                continue
            cleaned.append(p)
            prev = pl
        return " ".join(cleaned).strip()

    def _cluster_lines(ws: list[dict[str, Any]], *, y_tol: float) -> list[list[dict[str, Any]]]:
        ws = sorted(ws, key=lambda w: float(w["top"]))
        lines: list[list[dict[str, Any]]] = []
        last_y: float | None = None
        for w in ws:
            y = float(w["top"])
            if last_y is None or abs(y - last_y) > y_tol:
                lines.append([w])
                last_y = y
            else:
                lines[-1].append(w)
        return lines

    def _line_text(line: list[dict[str, Any]]) -> str:
        # left-to-right
        ws = sorted(line, key=lambda w: float(w["x0"]))
        return " ".join(((w.get("text") or "").strip()) for w in ws).strip()

    def _build_label_from_line(line: list[dict[str, Any]]) -> str:
        # Build label using words until the first day token appears.
        ws = sorted(line, key=lambda w: float(w["x0"]))
        parts: list[str] = []
        prev = None
        for w in ws:
            t = (w.get("text") or "").strip()
            if not t:
                continue
            if t.upper() in month_set:
                continue
            if _is_day_token(t):
                break
            tl = t.lower()
            if tl == prev:
                continue
            parts.append(t)
            prev = tl
        return _clean_row_label(" ".join(parts))

    def _extract_ophaaldata_dates(text: str) -> list[tuple[int, int]]:
        # returns [(day, month), ...]
        # tolerate double commas and extra spaces
        m = re.search(r"Ophaaldata:\s*([^.\n]+)", text, flags=re.IGNORECASE)
        if not m:
            return []
        raw = m.group(1)
        raw = raw.replace(",,", ",")
        items: list[tuple[int, int]] = []
        for part in raw.split(","):
            part = part.strip()
            dm = re.fullmatch(r"(\d{1,2})/(\d{1,2})", part)
            if not dm:
                continue
            items.append((int(dm.group(1)), int(dm.group(2))))
        return items

    import io

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=True) or []
            if not words:
                continue

            page_w = float(page.width)
            page_h = float(page.height)

            # -------------------------
            # 1) Month header detection
            # -------------------------
            month_words = []
            for w in words:
                t = (w.get("text") or "").strip().upper()
                if t in month_set:
                    cx = (float(w["x0"]) + float(w["x1"])) / 2.0
                    month_words.append((t, cx, float(w["top"])))

            month_words.sort(key=lambda x: x[1])

            boundaries: list[tuple[str, float, float]] = []
            table_top = page_h * 0.15
            table_bottom = page_h * 0.70

            if len(month_words) >= 10:
                centers = [cx for _, cx, _ in month_words]
                month_keys = [k for k, _, _ in month_words]
                month_tops = [top for _, _, top in month_words]
                # table starts shortly under month header row
                table_top = min(month_tops) + 8.0
                table_bottom = page_h * 0.70

                for i, c in enumerate(centers):
                    left = 0.0 if i == 0 else (centers[i - 1] + c) / 2.0
                    right = page_w if i == len(centers) - 1 else (c + centers[i + 1]) / 2.0
                    boundaries.append((month_keys[i], left, right))

            # ---------------------------------------------
            # 2) GRID/TABLE parsing (if we found month cols)
            # ---------------------------------------------
            if boundaries:
                # Candidate label words: left-ish, within table vertical span, not numbers/month headers
                # Keep a tighter left zone to avoid grabbing column day numbers
                label_x_limit = page_w * 0.30

                label_candidates = []
                for w in words:
                    txt = (w.get("text") or "").strip()
                    if not txt:
                        continue
                    x0 = float(w["x0"])
                    y = float(w["top"])
                    if x0 > label_x_limit:
                        continue
                    if y < table_top or y > table_bottom:
                        continue
                    if txt.upper() in month_set:
                        continue
                    if _is_day_token(txt):
                        continue
                    label_candidates.append(w)

                # Cluster into lines and build row anchors (label, y)
                lines = _cluster_lines(label_candidates, y_tol=3.0)
                row_anchors: list[tuple[str, float]] = []
                for line in lines:
                    label = _build_label_from_line(line)
                    if not label:
                        continue
                    # avoid clearly long sentences; labels are typically short
                    if len(label.split()) > 6:
                        continue
                    if not _has_letters(label):
                        continue
                    # reject obvious instruction lines even if short-ish
                    if label.lower().startswith(("zet ", "plaats ", "aanbied", "kijk ")):
                        continue
                    y = float(min(float(w["top"]) for w in line))
                    row_anchors.append((label, y))

                row_anchors.sort(key=lambda x: x[1])

                # Make y-bands and collect day numbers; keep only rows with days
                for i, (label, y) in enumerate(row_anchors):
                    y0 = y - 2.0
                    y1 = (row_anchors[i + 1][1] - 2.0) if i + 1 < len(row_anchors) else table_bottom
                    if y1 <= y0:
                        continue

                    row_items: list[dict[str, Any]] = []

                    for (mkey, x0, x1) in boundaries:
                        m = month_map[mkey]
                        for w in words:
                            txt = (w.get("text") or "").strip()
                            md = re.fullmatch(r"(\d{1,2})(\*)?", txt)
                            if not md:
                                continue
                            day = int(md.group(1))

                            wy = float(w["top"])
                            if wy < y0 or wy > y1:
                                continue

                            wc = (float(w["x0"]) + float(w["x1"])) / 2.0
                            if wc < x0 or wc > x1:
                                continue

                            try:
                                d = datetime(year, m, day).strftime("%Y-%m-%d")
                            except ValueError:
                                continue

                            row_items.append({"type": label, "date": d})

                    # Only keep rows that actually have day numbers
                    if row_items:
                        out.extend(row_items)

            # --------------------------------------------------
            # 3) "Ophaaldata:" sections (Textiel / Grofvuil / ...)
            # --------------------------------------------------
            # Strategy:
            # - Build left-column lines for the whole page (not only the table)
            # - Treat a line as a "section header" if it's short, has letters, and not "Ophaaldata:"
            # - For each header, look down until next header; if within that band there's Ophaaldata: parse dd/mm list
            left_limit = page_w * 0.45
            left_words = []
            for w in words:
                txt = (w.get("text") or "").strip()
                if not txt:
                    continue
                if float(w["x0"]) > left_limit:
                    continue
                # keep also lower part of page (instructions), we'll filter by "has Ophaaldata" later
                left_words.append(w)

            left_lines = _cluster_lines(left_words, y_tol=3.0)
            # make (y, text)
            left_line_items: list[tuple[float, str]] = []
            for line in left_lines:
                y = float(min(float(w["top"]) for w in line))
                text = _clean_row_label(_line_text(line))
                if text:
                    left_line_items.append((y, text))
            left_line_items.sort(key=lambda x: x[0])

            # pick headers
            headers: list[tuple[str, float]] = []
            for y, text in left_line_items:
                tl = text.lower()
                if "ophaaldata" in tl:
                    continue
                if len(text) < 2:
                    continue
                if len(text.split()) > 6:
                    continue
                if not _has_letters(text):
                    continue
                # skip address-like single words if they never get dates (will be filtered anyway)
                headers.append((text, y))

            # De-dup headers very close together (pdf duplication)
            dedup_headers: list[tuple[str, float]] = []
            last_y = None
            last_t = None
            for t, y in headers:
                if last_y is not None and abs(y - last_y) < 2.5 and last_t and t.lower() == last_t.lower():
                    continue
                dedup_headers.append((t, y))
                last_y = y
                last_t = t

            # Now for each header band, search for an Ophaaldata line in that band
            for i, (header, hy) in enumerate(dedup_headers):
                band_top = hy - 2.0
                band_bottom = (dedup_headers[i + 1][1] - 2.0) if i + 1 < len(dedup_headers) else page_h

                # collect all left-line texts in the band and join them
                band_text_parts = []
                for y, text in left_line_items:
                    if y < band_top or y > band_bottom:
                        continue
                    band_text_parts.append(text)
                band_text = " ".join(band_text_parts)

                pairs = _extract_ophaaldata_dates(band_text)
                if not pairs:
                    continue

                for day, month in pairs:
                    try:
                        d = datetime(year, month, day).strftime("%Y-%m-%d")
                    except ValueError:
                        continue
                    out.append({"type": header, "date": d})

    # Deduplicate (PDF extraction can yield duplicates)
    seen = set()
    deduped: list[dict[str, Any]] = []
    for item in out:
        key = (item.get("type"), item.get("date"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    return deduped


def _parse_waste_data_raw(
    waste_data_raw_temp: Sequence[dict[str, Any]],
) -> list[dict[str, str]]:
    waste_data_raw: list[dict[str, str]] = []

    for item in waste_data_raw_temp:
        date_str = item.get("date")
        if not date_str:
            continue

        waste_type = waste_type_rename((item.get("type") or "").strip().lower())
        if not waste_type:
            continue

        waste_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
        waste_data_raw.append({"type": waste_type, "date": waste_date})

    return waste_data_raw


def get_waste_data_raw(
    provider: str,
    postal_code: str,
    street_number: str,
    suffix: str,
    *,
    token: str | None = None,
    session: requests.Session | None = None,
    timeout: tuple[float, float] = _DEFAULT_TIMEOUT,
    verify: bool = False,
    device_id: str | None = None,
) -> list[dict[str, str]]:
    """Return waste_data_raw."""

    url = _build_url(provider, postal_code, street_number, suffix)
    session = session or requests.Session()

    try:
        token = _normalize_token(token)

        # New behavior: parse the PDF calendar.
        corrected_postal_code = format_postal_code_omrin(postal_code)
        year = datetime.now().year
        # Allow token to act as a year override if user passes "2026"
        if token:
            try:
                year = int(token)
            except Exception:
                pass

        pdf_url = (
            "https://www.omrin.nl/api/CalendarPdf"
            f"?zipCode={requests.utils.quote(corrected_postal_code)}"
            f"&houseNumber={requests.utils.quote(str(street_number))}"
            f"&year={year}"
        )

        _LOGGER.debug("Omrin: fetching CalendarPdf: %s", pdf_url)

        resp = session.get(
            pdf_url,
            headers={
                "User-Agent": "Mozilla/5.0 (HomeAssistant)",
                "Accept": "application/pdf",
            },
            timeout=timeout,
            verify=verify,
        )
        resp.raise_for_status()

        waste_data_raw_temp = _parse_calendar_pdf(resp.content, year=year)
        waste_data_raw = _parse_waste_data_raw(waste_data_raw_temp)
        return waste_data_raw

    except requests.exceptions.RequestException as err:
        _LOGGER.error("Omrin request error: %s", err)
        raise ValueError(err) from err
