from __future__ import annotations

import csv
import io
from typing import Any

RESULT_COLUMNS = (
    "tps_number",
    "tps_field",
    "tps_status",
    "tps_checked_at",
    "tps_message",
)


def first_result(item: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
    if item["status"] != "duplicate":
        return item
    number = item.get("normalized")
    for other in job["items"]:
        if (
            other.get("normalized") == number
            and other["status"] in {"on_tps", "not_on_tps", "failed"}
        ):
            return other
    return item


def resolved_status(item: dict[str, Any], job: dict[str, Any]) -> str:
    return first_result(item, job)["status"] if item["status"] == "duplicate" else item["status"]


def original_headers(job: dict[str, Any]) -> list[str]:
    headers = list(job.get("original_headers") or [])
    if headers:
        return headers
    seen: list[str] = []
    for item in job["items"]:
        for key in item.get("fields") or item.get("extra") or {}:
            if key not in seen:
                seen.append(key)
    return seen


def rows_for_status(job: dict[str, Any], status: str) -> list[dict[str, str]]:
    headers = original_headers(job)
    rows: list[dict[str, str]] = []
    for item in job["items"]:
        source = first_result(item, job)
        if resolved_status(item, job) != status:
            continue
        fields = item.get("fields") or item.get("extra") or {}
        row = {header: fields.get(header, "") for header in headers}
        row["tps_number"] = item.get("normalized") or ""
        row["tps_field"] = item.get("source_field") or ""
        row["tps_status"] = status
        row["tps_checked_at"] = source.get("checked_at") or ""
        row["tps_message"] = source.get("message") or ""
        rows.append(row)
    return rows


def csv_bytes(rows: list[dict[str, str]]) -> bytes:
    output = io.StringIO()
    if rows:
        fieldnames = [key for key in rows[0].keys()]
    else:
        fieldnames = list(RESULT_COLUMNS)
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")
