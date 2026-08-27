from __future__ import annotations

import re

import phonenumbers

UK_DIGIT_RE = re.compile(r"^0\d{9,10}$")
EMPTY_VALUES = {
    "",
    "-",
    "--",
    "n/a",
    "na",
    "none",
    "null",
    "nil",
    "unknown",
    "tbc",
    "0",
}
SCI_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?e[+-]?\d+$", re.I)
EXCEL_FLOAT_RE = re.compile(r"^\d+\.0+$")
CHUNK_RE = re.compile(r"(?:\+44|0044|44|0)?[1-9]\d{8,13}")


def is_blank(raw: str) -> bool:
    return (raw or "").strip().lower() in EMPTY_VALUES


def extract_candidate(raw: str) -> str:
    text = str(raw or "").strip()
    if EXCEL_FLOAT_RE.match(text):
        text = text.split(".", 1)[0]
    if SCI_RE.match(text):
        try:
            text = str(int(float(text)))
        except ValueError:
            pass
    text = text.replace("(0)", "")
    text = re.sub(r"[\s().\-]+", "", text)
    return text


def _try_parse(candidate: str) -> str | None:
    if not candidate:
        return None
    if candidate.startswith("00"):
        candidate = "+" + candidate[2:]
    if candidate.startswith("44") and not candidate.startswith("440"):
        candidate = "+" + candidate
    if re.fullmatch(r"[127]\d{8,9}", candidate):
        candidate = "0" + candidate

    try:
        parsed = phonenumbers.parse(candidate, "GB")
    except phonenumbers.NumberParseException:
        return None

    if phonenumbers.region_code_for_number(parsed) != "GB":
        return None
    if not (
        phonenumbers.is_valid_number(parsed) or phonenumbers.is_possible_number(parsed)
    ):
        return None

    national = phonenumbers.format_number(
        parsed, phonenumbers.PhoneNumberFormat.NATIONAL
    )
    digits = re.sub(r"\D", "", national)
    if not UK_DIGIT_RE.match(digits):
        return None
    if digits[1] not in {"1", "2", "3", "7"}:
        return None
    return digits


def normalize_uk_number(raw: str) -> str | None:
    """Return a TPS-ready UK number (leading 0, digits only) or None."""
    if raw is None or is_blank(str(raw)):
        return None

    text = str(raw).strip()
    tried: set[str] = set()
    for candidate in (extract_candidate(text), *CHUNK_RE.findall(extract_candidate(text))):
        if not candidate or candidate in tried:
            continue
        tried.add(candidate)
        result = _try_parse(candidate)
        if result:
            return result
    return None


def mask_number(number: str) -> str:
    digits = re.sub(r"\D", "", number or "")
    if len(digits) < 7:
        return "••••••••"
    return f"{digits[:4]}****{digits[-3:]}"
