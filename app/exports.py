from __future__ import annotations

import csv
import io
from typing import Any


def resolved_status(item: dict[str, Any], job: dict[str, Any]) -> str:
    if item["status"] != "duplicate":
        return item["status"]
    number = item.get("normalized")
    for other in job["items"]:
        if (
            other.get("normalized") == number
            and other["status"] in {"on_tps", "not_on_tps", "failed"}
        ):
            return other["status"]
    return "duplicate"


def rows_for_status(job: dict[str, Any], status: str) -> list[dict[str, str]]:
    extra_keys: list[str] = []
    for item in job["items"]:
        for key in item.get("extra") or {}:
            if key not in extra_keys:
                extra_keys.append(key)

    rows: list[dict[str, str]] = []
    for item in job["items"]:
        if resolved_status(item, job) != status:
            continue
        row = {
            "phone": item.get("normalized") or "",
            "original": item.get("original") or "",
            "tps_status": status,
            "checked_at": item.get("checked_at") or "",
            "message": item.get("message") or "",
        }
        for key in extra_keys:
            row[key] = (item.get("extra") or {}).get(key, "")
        rows.append(row)
    return rows


def csv_bytes(rows: list[dict[str, str]]) -> bytes:
    output = io.StringIO()
    fieldnames = (
        ["phone", "original", "tps_status", "checked_at", "message"]
        + [key for key in (rows[0].keys() if rows else []) if key not in {
            "phone", "original", "tps_status", "checked_at", "message"
        }]
    )
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")
