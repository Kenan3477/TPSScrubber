from __future__ import annotations

import re

import phonenumbers

UK_DIGIT_RE = re.compile(r"^0\d{9,10}$")


def extract_candidate(raw: str) -> str:
    text = (raw or "").strip()
    text = text.replace("(0)", "")
    text = re.sub(r"[\s().\-]+", "", text)
    return text


def normalize_uk_number(raw: str) -> str | None:
    """Return a TPS-ready UK number (leading 0, digits only) or None."""
    candidate = extract_candidate(raw)
    if not candidate:
        return None

    if candidate.startswith("00"):
        candidate = "+" + candidate[2:]

    try:
        parsed = phonenumbers.parse(candidate, "GB")
    except phonenumbers.NumberParseException:
        return None

    if phonenumbers.region_code_for_number(parsed) != "GB":
        return None
    if not phonenumbers.is_valid_number(parsed):
        return None

    national = phonenumbers.format_number(
        parsed, phonenumbers.PhoneNumberFormat.NATIONAL
    )
    digits = re.sub(r"\D", "", national)
    if not UK_DIGIT_RE.match(digits):
        return None
    return digits


def mask_number(number: str) -> str:
    digits = re.sub(r"\D", "", number or "")
    if len(digits) < 7:
        return "••••••••"
    return f"{digits[:4]}****{digits[-3:]}"
