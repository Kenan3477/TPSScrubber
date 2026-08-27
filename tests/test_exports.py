from app.exports import rows_for_status
from app.parser import parse_number_file
from app.store import create_job


def test_duplicate_rows_follow_first_result():
    parsed = parse_number_file("numbers.txt", b"07123456789\n07123456789\n")
    job = create_job("numbers.txt", parsed)
    job["items"][0]["status"] = "on_tps"
    job["items"][0]["message"] = "Phone number is registered"
    job["items"][0]["checked_at"] = "2026-08-27T09:00:00+00:00"

    on_tps = rows_for_status(job, "on_tps")
    assert len(on_tps) == 2
    assert on_tps[0]["tps_number"] == "07123456789"
    assert on_tps[1]["tps_number"] == "07123456789"
    assert on_tps[1]["tps_message"] == "Phone number is registered"
    assert on_tps[1]["tps_checked_at"] == "2026-08-27T09:00:00+00:00"


def test_exports_keep_every_original_crm_column():
    parsed = parse_number_file(
        "crm.csv",
        b"Contact ID,First Name,Email,Mobile,Landline,Owner\n"
        b"1001,Jane,jane@acme.test,7487723751,02079460958,Sam\n",
    )
    job = create_job("crm.csv", parsed)
    job["items"][0]["status"] = "not_on_tps"
    job["items"][0]["message"] = "Phone number is not registered"
    job["items"][1]["status"] = "on_tps"
    job["items"][1]["message"] = "Phone number is registered"

    not_on = rows_for_status(job, "not_on_tps")
    on_tps = rows_for_status(job, "on_tps")
    assert list(not_on[0].keys())[:6] == [
        "Contact ID",
        "First Name",
        "Email",
        "Mobile",
        "Landline",
        "Owner",
    ]
    assert not_on[0]["Contact ID"] == "1001"
    assert not_on[0]["Email"] == "jane@acme.test"
    assert not_on[0]["Mobile"] == "7487723751"
    assert not_on[0]["Landline"] == "02079460958"
    assert not_on[0]["tps_number"] == "07487723751"
    assert not_on[0]["tps_field"] == "Mobile"
    assert on_tps[0]["tps_number"] == "02079460958"
    assert on_tps[0]["tps_field"] == "Landline"
    assert on_tps[0]["First Name"] == "Jane"
