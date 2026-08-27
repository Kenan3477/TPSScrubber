from app.exports import rows_for_status
from app.parser import parse_number_file
from app.store import create_job


def test_duplicate_rows_follow_first_result():
    rows = parse_number_file(
        "numbers.txt",
        b"07123456789\n07123456789\n",
    )
    job = create_job("numbers.txt", rows)
    job["items"][0]["status"] = "on_tps"
    job["items"][0]["message"] = "Phone number is registered"
    job["items"][0]["checked_at"] = "2026-08-27T09:00:00+00:00"

    on_tps = rows_for_status(job, "on_tps")
    assert len(on_tps) == 2
    assert on_tps[0]["phone"] == "07123456789"
    assert on_tps[1]["phone"] == "07123456789"
    assert on_tps[1]["message"] == "Phone number is registered"
    assert on_tps[1]["checked_at"] == "2026-08-27T09:00:00+00:00"
