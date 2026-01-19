"""Afvalwijzer integration."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import suppress
from datetime import datetime
import io
import re
from typing import Any

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


def _extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes using pypdf."""
    if PdfReader is None:
        return ""

    with suppress(Exception):
        reader = PdfReader(io.BytesIO(pdf_bytes))
        return "\n".join((p.extract_text() or "") for p in reader.pages)

    return ""


# -------------------------
# PDF parsing helper funcs
# -------------------------

_MONTH_MAP: dict[str, int] = {
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
_MONTH_SET = set(_MONTH_MAP.keys())


def _is_day_token(txt: str) -> bool:
    return bool(re.fullmatch(r"\d{1,2}(\*)?", txt.strip()))


def _has_letters(txt: str) -> bool:
    return bool(re.search(r"[A-Za-zÀ-ÿ]", txt))


def _looks_like_url(text: str) -> bool:
    t = text.strip().lower()
    return (
        "http://" in t
        or "https://" in t
        or "www." in t
        or bool(re.search(r"\b[a-z0-9.-]+\.(nl|com|net|org|eu)\b", t))
        or bool("/" in t and re.search(r"\.[a-z]{2,4}/", t))
    )


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
    ws = sorted(line, key=lambda w: float(w["x0"]))
    return " ".join(((w.get("text") or "").strip()) for w in ws).strip()


def _build_label_from_line(line: list[dict[str, Any]]) -> str:
    """Build a row label from a line by stopping at the first day-number token."""
    ws = sorted(line, key=lambda w: float(w["x0"]))
    parts: list[str] = []
    prev = None
    for w in ws:
        t = (w.get("text") or "").strip()
        if not t:
            continue
        if t.upper() in _MONTH_SET:
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
    m = re.search(r"Ophaaldata:\s*([^.\n]+)", text, flags=re.IGNORECASE)
    if not m:
        return []
    raw = m.group(1).replace(",,", ",")
    items: list[tuple[int, int]] = []
    for part in raw.split(","):
        part = part.strip()
        dm = re.fullmatch(r"(\d{1,2})/(\d{1,2})", part)
        if not dm:
            continue
        items.append((int(dm.group(1)), int(dm.group(2))))
    return items


def _month_boundaries(words: list[dict[str, Any]], *, page_w: float, page_h: float) -> tuple[
    list[tuple[str, float, float]],
    float,
    float,
]:
    month_words: list[tuple[str, float, float]] = []
    for w in words:
        t = (w.get("text") or "").strip().upper()
        if t in _MONTH_SET:
            cx = (float(w["x0"]) + float(w["x1"])) / 2.0
            month_words.append((t, cx, float(w["top"])))
    month_words.sort(key=lambda x: x[1])

    table_top = page_h * 0.15
    table_bottom = page_h * 0.70
    boundaries: list[tuple[str, float, float]] = []

    if len(month_words) >= 10:
        centers = [cx for _, cx, _ in month_words]
        month_keys = [k for k, _, _ in month_words]
        month_tops = [top for _, _, top in month_words]
        table_top = min(month_tops) + 8.0

        for i, c in enumerate(centers):
            left = 0.0 if i == 0 else (centers[i - 1] + c) / 2.0
            right = page_w if i == len(centers) - 1 else (c + centers[i + 1]) / 2.0
            boundaries.append((month_keys[i], left, right))

    return boundaries, table_top, table_bottom


def _parse_grid_rows(
    words: list[dict[str, Any]],
    *,
    boundaries: list[tuple[str, float, float]],
    table_top: float,
    table_bottom: float,
    page_w: float,
    year: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not boundaries:
        return out

    label_x_limit = page_w * 0.30
    label_candidates: list[dict[str, Any]] = []
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
        if txt.upper() in _MONTH_SET:
            continue
        if _is_day_token(txt):
            continue
        label_candidates.append(w)

    lines = _cluster_lines(label_candidates, y_tol=3.0)
    row_anchors: list[tuple[str, float]] = []
    for line in lines:
        label = _build_label_from_line(line)
        if not label:
            continue
        if len(label.split()) > 6:
            continue
        if not _has_letters(label):
            continue
        if label.lower().startswith(("zet ", "plaats ", "aanbied", "kijk ")):
            continue
        y = float(min(float(w["top"]) for w in line))
        row_anchors.append((label, y))

    row_anchors.sort(key=lambda x: x[1])

    for i, (label, y) in enumerate(row_anchors):
        y0 = y - 2.0
        y1 = (row_anchors[i + 1][1] - 2.0) if i + 1 < len(row_anchors) else table_bottom
        if y1 <= y0:
            continue

        row_items: list[dict[str, Any]] = []
        for (mkey, x0, x1) in boundaries:
            m = _MONTH_MAP[mkey]
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

                with suppress(ValueError):
                    d = datetime(year, m, day).strftime("%Y-%m-%d")
                    row_items.append({"type": label, "date": d})

        if row_items:
            out.extend(row_items)

    return out


def _parse_ophaaldata_sections(
    words: list[dict[str, Any]],
    *,
    page_w: float,
    page_h: float,
    year: int,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    left_limit = page_w * 0.55  # iets ruimer zodat "Ophaaldata:" regel altijd mee is
    left_words: list[dict[str, Any]] = []
    for w in words:
        txt = (w.get("text") or "").strip()
        if not txt:
            continue
        if float(w["x0"]) > left_limit:
            continue
        left_words.append(w)

    left_lines = _cluster_lines(left_words, y_tol=3.0)

    # maak (y, text) regels
    lines: list[tuple[float, str]] = []
    for line in left_lines:
        y = float(min(float(w["top"]) for w in line))
        text = _clean_row_label(_line_text(line))
        if text:
            lines.append((y, text))
    lines.sort(key=lambda x: x[0])

    def _is_bad_header(text: str) -> bool:
        tl = text.lower().strip()

        bad_starts = (
            "kijk",
            "meer",
            "informatie",
            "info",
            "aanmelden",
            "betaling",
            "ophalen",
            "breng",
            "let op",
            "zet ",
            "plaats ",
        )

        return (
            "ophaaldata" in tl
            or _looks_like_url(text)
            or tl.startswith(bad_starts)
            or bool("." in tl and len(tl.split()) >= 3)
        )

    # 1) vind alle Ophaaldata-regels
    ophaal_lines: list[tuple[float, str]] = []
    for y, text in lines:
        if "ophaaldata" in text.lower():
            ophaal_lines.append((y, text))

    # 2) per Ophaaldata regel: zoek kopregel erboven
    for oy, otext in ophaal_lines:
        pairs = _extract_ophaaldata_dates(otext)
        if not pairs:
            # soms staat de lijst op de volgende regel(s); pak klein window
            window_text = otext
            for y, text in lines:
                if y > oy and y < oy + 30:  # ~30pt onder de regel
                    window_text = f"{window_text} {text}"
            pairs = _extract_ophaaldata_dates(window_text)
            if not pairs:
                continue

        header: str | None = None
        # zoek omhoog: eerste geldige kopregel
        for y, text in reversed(lines):
            if y >= oy:
                continue
            if len(text) < 2 or len(text.split()) > 6:
                continue
            if not _has_letters(text):
                continue
            if _is_bad_header(text):
                continue
            header = text
            break

        if not header:
            continue  # geen kop gevonden => liever overslaan dan rommel-type

        for day, month in pairs:
            with suppress(ValueError):
                d = datetime(year, month, day).strftime("%Y-%m-%d")
                out.append({"type": header, "date": d})

    return out


def _parse_calendar_pdf(
    pdf_bytes: bytes,
    *,
    year: int,
) -> list[dict[str, Any]]:
    """Parse the Omrin CalendarPdf.

    Returns a list like: [{"date": "YYYY-MM-DD", "type": "<raw label>"}]
    """
    out: list[dict[str, Any]] = []

    if pdfplumber is None:
        text_all = _extract_text_from_pdf_bytes(pdf_bytes)
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
                with suppress(ValueError):
                    d = datetime(year, month, day).strftime("%Y-%m-%d")
                    out.append({"type": "ophaaldata", "date": d})
        return _dedupe_type_date(out)

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            words = page.extract_words(use_text_flow=True) or []
            if not words:
                continue

            page_w = float(page.width)
            page_h = float(page.height)

            boundaries, table_top, table_bottom = _month_boundaries(
                words, page_w=page_w, page_h=page_h
            )

            out.extend(
                _parse_grid_rows(
                    words,
                    boundaries=boundaries,
                    table_top=table_top,
                    table_bottom=table_bottom,
                    page_w=page_w,
                    year=year,
                )
            )

            out.extend(
                _parse_ophaaldata_sections(
                    words,
                    page_w=page_w,
                    page_h=page_h,
                    year=year,
                )
            )

    return _dedupe_type_date(out)


def _dedupe_type_date(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str | None, str | None]] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
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

        # Extra safety: skip any non-ISO date strings (e.g. "geen")
        if not isinstance(date_str, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_str):
            continue

        waste_type = waste_type_rename((item.get("type") or "").strip().lower())
        if not waste_type:
            continue

        waste_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
        waste_data_raw.append({"type": waste_type, "date": waste_date})

    return waste_data_raw


_LAST_GOOD_WASTE_DATA_RAW: list[dict[str, str]] = []


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
    del device_id  # not used in CalendarPdf flow; keep signature stable

    session = session or requests.Session()
    token = _normalize_token(token)

    # Always set year first (fixes "cannot access local variable 'year'")
    year = datetime.now().year
    if token:
        with suppress(ValueError, TypeError):
            year = int(token)

    try:
        corrected_postal_code = format_postal_code_omrin(postal_code)
        corrected_postal_code = (
            corrected_postal_code.strip().upper().replace(" ", "%20")
        )

        # IMPORTANT:
        # Do NOT quote() this again; %20 would become %2520.
        pdf_url = (
            "https://www.omrin.nl/api/CalendarPdf"
            f"?zipCode={corrected_postal_code}"
            f"&houseNumber={street_number}"
            f"&year={year}"
        )

        _LOGGER.debug(
            "Omrin: fetching CalendarPdf: %s (raw_zip=%s normalized_zip=%s)",
            pdf_url,
            postal_code,
            corrected_postal_code,
        )

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
        return _parse_waste_data_raw(waste_data_raw_temp)

    except requests.exceptions.RequestException as err:
        _LOGGER.error("Omrin request error: %s", err)
        raise ValueError(err) from err
