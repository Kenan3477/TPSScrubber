from app.exports import rows_for_status
from app.parser import parse_number_file
from app.store import create_job


CRM = (
    b"Status,Residential Status,First Name,Mobile,Landline\n"
    b"Active,Home Owner,Jane,07123456789,02079460958\n"
    b"Inactive,Tenant,John,07123456780,01912345678\n"
    b"Cancelled,Home Owner,Pat,07487723751,\n"
)


def test_only_active_customers_are_queued():
    parsed = parse_number_file("crm.csv", CRM)
    job = create_job("crm.csv", parsed)
    assert job["status_field"] == "Status"
    assert job["status_filter"] == "Active"
    pending = [item for item in job["items"] if item["status"] == "pending"]
    skipped = [item for item in job["items"] if item["status"] == "skipped"]
    assert {item["normalized"] for item in pending} == {"07123456789", "02079460958"}
    assert all(
        (item["fields"]["Status"] or "").lower() != "active" for item in skipped
    )
    assert job["stats"]["valid"] == 2
    assert job["stats"]["skipped"] > 0


def test_skipped_rows_are_not_exported_as_results():
    parsed = parse_number_file("crm.csv", CRM)
    job = create_job("crm.csv", parsed)
    for item in job["items"]:
        if item["status"] == "pending":
            item["status"] = "not_on_tps"
    exported = rows_for_status(job, "not_on_tps")
    assert exported
    phones = {row["tps_number"] for row in exported}
    assert "07123456780" not in phones
    assert "07487723751" not in phones
