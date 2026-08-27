from __future__ import annotations

import threading
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from app.exports import csv_bytes, rows_for_status
from app.parser import parse_number_file
from app.scanner import run_job
from app.store import create_job, load_job, public_job, save_job, utc_now

STATIC_DIR = Path(__file__).resolve().parent / "static"
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_SOURCE_ROWS = 20000
MAX_NUMBERS = 20000
ALLOWED_SUFFIXES = {".csv", ".txt", ".xlsx", ".xlsm"}

app = FastAPI(title="TPS Scrubber")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/jobs")
async def upload_job(file: UploadFile = File(...)) -> dict:
    filename = file.filename or "numbers.csv"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(400, "Upload a CSV, TXT, or Excel file.")

    content = await file.read()
    if not content:
        raise HTTPException(400, "The file is empty.")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(400, "File is larger than 25 MB.")

    parsed = parse_number_file(filename, content)
    if not parsed.source_rows:
        raise HTTPException(400, "No rows found in that file.")
    if parsed.source_rows > MAX_SOURCE_ROWS:
        raise HTTPException(
            400, f"This portal accepts up to {MAX_SOURCE_ROWS:,} rows per file."
        )
    unique_numbers = len({row.normalized for row in parsed.items if row.normalized})
    if unique_numbers > MAX_NUMBERS:
        raise HTTPException(
            400, f"This portal accepts up to {MAX_NUMBERS:,} phone numbers per file."
        )
    if not parsed.phone_fields:
        raise HTTPException(400, "Could not find a mobile or landline column in that file.")

    job = create_job(filename, parsed)
    return public_job(job)


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = load_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    return public_job(job)


@app.post("/api/jobs/{job_id}/start")
def start_job(job_id: str) -> dict:
    job = load_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    if job["status"] == "running":
        raise HTTPException(409, "This scan is already running.")
    if job["stats"]["valid"] == 0:
        raise HTTPException(400, "There are no valid UK numbers to check.")
    pending = any(item["status"] == "pending" for item in job["items"])
    if not pending and job["status"] == "complete":
        raise HTTPException(400, "This file has already been scanned.")

    job["status"] = "running"
    job["error"] = ""
    job["started_at"] = job.get("started_at") or utc_now()
    save_job(job)
    thread = threading.Thread(target=run_job, args=(job_id,), daemon=True)
    thread.start()
    return public_job(job)


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict:
    job = load_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    if job["status"] not in {"running", "paused"}:
        raise HTTPException(400, "This scan is not running.")
    job["status"] = "cancelled"
    job["current_number"] = None
    job["wait_until"] = None
    job["wait_reason"] = ""
    save_job(job)
    return public_job(job)


@app.get("/api/jobs/{job_id}/download/{bundle}")
def download_job(job_id: str, bundle: str) -> Response:
    mapping = {
        "on-tps": ("on_tps", "on_tps.csv"),
        "not-on-tps": ("not_on_tps", "not_on_tps.csv"),
        "failed": ("failed", "failed_or_invalid.csv"),
    }
    if bundle not in mapping:
        raise HTTPException(404, "Unknown download.")
    job = load_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")

    status, filename = mapping[bundle]
    if bundle == "failed":
        rows = rows_for_status(job, "failed") + rows_for_status(job, "invalid")
    else:
        rows = rows_for_status(job, status)
    return Response(
        content=csv_bytes(rows),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
