from app.store import create_job, load_job, pause_stale_running_jobs
from app.parser import parse_number_file


def test_pause_stale_running_jobs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("app.store.DATA_DIR", tmp_path / "data")
    monkeypatch.setattr("app.store.JOBS_DIR", tmp_path / "data" / "jobs")
    monkeypatch.setattr("app.store.UPLOADS_DIR", tmp_path / "data" / "uploads")

    parsed = parse_number_file("n.txt", b"07123456789\n")
    job = create_job("n.txt", parsed)
    job["status"] = "running"
    from app.store import save_job

    save_job(job)
    assert pause_stale_running_jobs() == 1
    fresh = load_job(job["id"])
    assert fresh["status"] == "paused"
    assert "restarted" in fresh["error"].lower()
