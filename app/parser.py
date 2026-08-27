from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import load_workbook

from app.numbers import normalize_uk_number

PHONE_HEADERS = {
    "phone",
    "phone_number",
    "phonenumber",
    "telephone",
    "telephone_number",
    "tel",
    "mobile",
    "mobile_number",
    "number",
    "msisdn",
    "contact",
    "contact_number",
}


@dataclass
class ParsedRow:
    source_row: int
    original: str
    normalized: str | None
    extra: dict[str, str] = field(default_factory=dict)


def _looks_like_phone(value: str) -> bool:
    return normalize_uk_number(value) is not None


def _pick_phone_column(headers: list[str], sample_rows: list[list[str]]) -> int:
    normalized = [re_header(h) for h in headers]
    for idx, name in enumerate(normalized):
        if name in PHONE_HEADERS:
            return idx

    best_idx = 0
    best_hits = -1
    width = max((len(row) for row in sample_rows), default=len(headers))
    for idx in range(width):
        hits = 0
        for row in sample_rows:
            if idx < len(row) and _looks_like_phone(row[idx]):
                hits += 1
        if hits > best_hits:
            best_hits = hits
            best_idx = idx
    return best_idx


def re_header(value: str) -> str:
    return "".join(ch for ch in (value or "").strip().lower() if ch.isalnum() or ch == "_")


def _rows_from_csv(content: bytes) -> tuple[list[str] | None, list[list[str]]]:
    text = content.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return None, []
    header_hits = sum(1 for cell in rows[0] if re_header(cell) in PHONE_HEADERS)
    if header_hits or any(not _looks_like_phone(cell) and re_header(cell) for cell in rows[0]):
        if any(re_header(cell) in PHONE_HEADERS or not _looks_like_phone(cell) for cell in rows[0]):
            # Treat as header if any cell is clearly a label rather than a number.
            if not all(_looks_like_phone(cell) or not cell.strip() for cell in rows[0]):
                return [cell.strip() for cell in rows[0]], rows[1:]
    return None, rows


def _rows_from_xlsx(content: bytes) -> tuple[list[str] | None, list[list[str]]]:
    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    sheet = workbook.active
    rows: list[list[str]] = []
    for row in sheet.iter_rows(values_only=True):
        values = ["" if cell is None else str(cell).strip() for cell in row]
        if any(values):
            rows.append(values)
    workbook.close()
    if not rows:
        return None, []
    if not all(_looks_like_phone(cell) or not cell for cell in rows[0]):
        return [cell.strip() for cell in rows[0]], rows[1:]
    return None, rows


def _rows_from_txt(content: bytes) -> tuple[list[str] | None, list[list[str]]]:
    text = content.decode("utf-8-sig", errors="replace")
    rows: list[list[str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if "," in line or "\t" in line:
            parts = [part.strip() for part in re_split_line(line)]
            rows.append(parts)
        else:
            rows.append([line])
    if not rows:
        return None, []
    if len(rows[0]) > 1 and not all(_looks_like_phone(cell) or not cell for cell in rows[0]):
        return [cell.strip() for cell in rows[0]], rows[1:]
    return None, rows


def re_split_line(line: str) -> list[str]:
    if "\t" in line:
        return line.split("\t")
    return next(csv.reader([line]))


def parse_number_file(filename: str, content: bytes) -> list[ParsedRow]:
    suffix = Path(filename).suffix.lower()
    if suffix in {".xlsx", ".xlsm"}:
        headers, rows = _rows_from_xlsx(content)
    elif suffix in {".csv"}:
        headers, rows = _rows_from_csv(content)
    else:
        headers, rows = _rows_from_txt(content)

    if not rows:
        return []

    phone_idx = _pick_phone_column(headers or [], rows[:25])
    parsed: list[ParsedRow] = []
    for offset, row in enumerate(rows, start=2 if headers else 1):
        original = row[phone_idx].strip() if phone_idx < len(row) else ""
        extra: dict[str, str] = {}
        if headers:
            for idx, header in enumerate(headers):
                if idx == phone_idx or not header:
                    continue
                extra[header] = row[idx] if idx < len(row) else ""
        parsed.append(
            ParsedRow(
                source_row=offset,
                original=original,
                normalized=normalize_uk_number(original) if original else None,
                extra=extra,
            )
        )
    return parsed
