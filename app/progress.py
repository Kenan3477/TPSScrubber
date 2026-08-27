from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

DEFAULT_PACE_SECONDS = 20.0


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def job_progress(job: dict[str, Any], now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    started = parse_iso(job.get("started_at"))
    elapsed = max(0.0, (now - started).total_seconds()) if started else 0.0
    checked = int(job.get("checked") or 0)
    total = int(job.get("total_to_check") or 0)
    remaining = max(0, total - checked)
    wait_until = parse_iso(job.get("wait_until"))
    wait_seconds = max(0.0, (wait_until - now).total_seconds()) if wait_until else 0.0

    if checked >= 1 and elapsed > 0:
        pace = elapsed / checked
    else:
        pace = DEFAULT_PACE_SECONDS

    running = job.get("status") == "running"
    eta = (remaining * pace + wait_seconds) if running else 0.0
    percent = int(min(100, round(100 * checked / total))) if total else 0

    return {
        "elapsed_seconds": int(elapsed),
        "eta_seconds": int(eta),
        "wait_seconds": int(wait_seconds),
        "wait_reason": job.get("wait_reason") or "",
        "wait_until": job.get("wait_until"),
        "seconds_per_check": round(pace, 1),
        "remaining": remaining,
        "percent": percent,
        "started_at": job.get("started_at"),
    }
