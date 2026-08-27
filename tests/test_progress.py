from datetime import datetime, timezone

from app.progress import job_progress


def test_eta_uses_observed_pace_and_current_wait():
    now = datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc)
    job = {
        "status": "running",
        "checked": 10,
        "total_to_check": 110,
        "started_at": "2026-08-27T11:50:00+00:00",
        "wait_until": "2026-08-27T12:01:00+00:00",
        "wait_reason": "TPS rate limit",
    }
    progress = job_progress(job, now=now)
    assert progress["elapsed_seconds"] == 600
    assert progress["seconds_per_check"] == 60.0
    assert progress["remaining"] == 100
    assert progress["wait_seconds"] == 60
    assert progress["eta_seconds"] == 100 * 60 + 60
    assert progress["percent"] == 9


def test_eta_is_zero_when_not_running():
    job = {
        "status": "complete",
        "checked": 10,
        "total_to_check": 10,
        "started_at": "2026-08-27T11:50:00+00:00",
    }
    progress = job_progress(job, now=datetime(2026, 8, 27, 12, 0, tzinfo=timezone.utc))
    assert progress["eta_seconds"] == 0
    assert progress["percent"] == 100
