from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.parser import ParsedFile
from app.progress import job_progress

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
JOBS_DIR = DATA_DIR / "jobs"
UPLOADS_DIR = DATA_DIR / "uploads"

_lock = threading.Lock()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _job_path(job_id: str) -> Path:
    return JOBS_DIR / f"{job_id}.json"


def create_job(filename: str, parsed: ParsedFile) -> dict[str, Any]:
    ensure_dirs()
    seen: dict[str, int] = {}
    items: list[dict[str, Any]] = []
    valid = 0
    invalid = 0
    duplicates = 0

    for row in parsed.items:
        item = {
            "source_row": row.source_row,
            "source_field": row.source_field,
            "original": row.original,
            "normalized": row.normalized,
            "fields": row.fields,
            "status": "pending",
            "message": "",
            "checked_at": None,
        }
        if not row.normalized:
            item["status"] = "invalid"
            item["message"] = "Could not read a UK phone number"
            invalid += 1
        elif row.normalized in seen:
            item["status"] = "duplicate"
            item["message"] = f"Same number as row {seen[row.normalized]}"
            duplicates += 1
        else:
            seen[row.normalized] = row.source_row
            valid += 1
        items.append(item)

    job = {
        "id": uuid4().hex,
        "filename": filename,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "status": "ready",
        "error": "",
        "checked": 0,
        "total_to_check": valid,
        "current_number": None,
        "started_at": None,
        "wait_until": None,
        "wait_reason": "",
        "original_headers": parsed.headers,
        "phone_fields": parsed.phone_fields,
        "source_rows": parsed.source_rows,
        "items": items,
        "stats": {
            "rows": parsed.source_rows,
            "valid": valid,
            "invalid": invalid,
            "duplicates": duplicates,
            "on_tps": 0,
            "not_on_tps": 0,
            "failed": 0,
        },
    }
    save_job(job)
    return job


def save_job(job: dict[str, Any]) -> None:
    ensure_dirs()
    job["updated_at"] = utc_now()
    path = _job_path(job["id"])
    tmp = path.with_suffix(".tmp")
    with _lock:
        tmp.write_text(json.dumps(job, indent=2), encoding="utf-8")
        tmp.replace(path)


def load_job(job_id: str) -> dict[str, Any] | None:
    path = _job_path(job_id)
    if not path.exists():
        return None
    with _lock:
        return json.loads(path.read_text(encoding="utf-8"))


def public_job(job: dict[str, Any]) -> dict[str, Any]:
    preview = []
    for item in job["items"][:8]:
        preview.append(
            {
                "original": item["original"],
                "normalized": item["normalized"],
                "source_field": item.get("source_field") or "",
                "status": item["status"],
            }
        )
    return {
        "id": job["id"],
        "filename": job["filename"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
        "status": job["status"],
        "error": job["error"],
        "checked": job["checked"],
        "total_to_check": job["total_to_check"],
        "current_number": job["current_number"],
        "phone_fields": job.get("phone_fields") or [],
        "source_rows": job.get("source_rows", job["stats"].get("rows", 0)),
        "stats": job["stats"],
        "preview": preview,
        **job_progress(job),
    }


def recount_stats(job: dict[str, Any]) -> None:
    stats = {
        "rows": len(job["items"]),
        "valid": 0,
        "invalid": 0,
        "duplicates": 0,
        "on_tps": 0,
        "not_on_tps": 0,
        "failed": 0,
    }
    checked = 0
    for item in job["items"]:
        status = item["status"]
        if status == "invalid":
            stats["invalid"] += 1
        elif status == "duplicate":
            stats["duplicates"] += 1
        elif status in {"pending", "on_tps", "not_on_tps", "failed"}:
            stats["valid"] += 1
        if status == "on_tps":
            stats["on_tps"] += 1
            checked += 1
        elif status == "not_on_tps":
            stats["not_on_tps"] += 1
            checked += 1
        elif status == "failed":
            stats["failed"] += 1
            checked += 1
    stats["rows"] = job.get("source_rows", stats["rows"])
    job["stats"] = stats
    job["checked"] = checked
    job["total_to_check"] = stats["valid"]

