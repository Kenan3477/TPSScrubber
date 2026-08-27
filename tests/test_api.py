from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_upload_counts_valid_invalid_and_duplicates():
    response = client.post(
        "/api/jobs",
        files={"file": ("numbers.txt", b"07123456789\n07123456789\nbad\n", "text/plain")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["stats"]["rows"] == 3
    assert data["stats"]["valid"] == 1
    assert data["stats"]["duplicates"] == 1
    assert data["stats"]["invalid"] == 1
    assert data["total_to_check"] == 1
    assert data["status"] == "ready"


def test_rejects_empty_file():
    response = client.post(
        "/api/jobs",
        files={"file": ("empty.csv", b"", "text/csv")},
    )
    assert response.status_code == 400
